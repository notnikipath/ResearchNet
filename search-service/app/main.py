from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.researchnet_common import (
    PaperDocument,
    PaperLanguage,
    PaperStatus,
    Role,
    SearchHit,
    SearchMode,
    SearchQualityReport,
    SearchRequest,
    SearchResponse,
    Settings,
    TTLCache,
    build_audit_event,
    has_permission,
    ndcg_at_k,
    normalize_text,
    precision_at_k,
    semantic_score,
    tokenize,
)

settings = Settings(service_name="search-service", service_port=8502)
app = FastAPI(title="ResearchNet Search Service", version="1.0.0")


class BulkIndexRequest(BaseModel):
    papers: list[PaperDocument] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class QualityEvalRequest(BaseModel):
    ranked_ids: list[str]
    relevant_ids: list[str]


index_store: dict[str, PaperDocument] = {}
index_queue: list[dict] = []
search_cache = TTLCache(ttl_seconds=180)
audit_log: list[dict] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="search",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _paper_matches_filters(paper: PaperDocument, request: SearchRequest) -> bool:
    filters = request.filters
    if filters.author_id and all(author.author_id != filters.author_id for author in paper.authors):
        return False
    if filters.year_from and paper.year < filters.year_from:
        return False
    if filters.year_to and paper.year > filters.year_to:
        return False
    if filters.journal and normalize_text(filters.journal) not in normalize_text(paper.source_name):
        return False
    if filters.citations_min is not None and paper.citations_count < filters.citations_min:
        return False
    if filters.source_types and paper.source_type not in filters.source_types:
        return False
    if filters.language and paper.language != filters.language:
        return False
    return True


def _fulltext_score(query: str, paper: PaperDocument) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    searchable = f"{paper.title} {paper.abstract} {' '.join(paper.keywords)} {' '.join(paper.topics)}"
    paper_tokens = set(tokenize(searchable))
    overlap = len(query_tokens & paper_tokens) / max(len(query_tokens), 1)
    citation_bonus = min(paper.citations_count / 200, 0.35)
    recency_bonus = max(0, 1 - (datetime.now(UTC).year - paper.year) * 0.05)
    return round(overlap * 0.65 + citation_bonus + recency_bonus * 0.2, 6)


def _semantic_score(query: str, paper: PaperDocument) -> float:
    body = f"{paper.title}. {paper.abstract}. {' '.join(paper.keywords)}"
    topic_text = " ".join(paper.topics)
    return round(semantic_score(query, f"{body} {topic_text}") * 0.85 + min(paper.citations_count / 400, 0.15), 6)


def _rank(request: SearchRequest) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for paper in index_store.values():
        if not _paper_matches_filters(paper, request):
            continue
        if request.mode == SearchMode.SEMANTIC:
            score = _semantic_score(request.query, paper)
        else:
            score = _fulltext_score(request.query, paper)
        if score <= 0:
            continue
        snippet_source = paper.summary or paper.abstract
        snippet = snippet_source[:240]
        hits.append(
            SearchHit(
                paper_id=paper.paper_id,
                score=score,
                title=paper.title,
                snippet=snippet,
                authors=[author.name for author in paper.authors],
                year=paper.year,
                source_name=paper.source_name,
            )
        )
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[: request.limit]


def _cache_key(request: SearchRequest) -> str:
    return request.model_dump_json()


def _async_apply_bulk(queue_id: str, papers: list[PaperDocument]) -> None:
    for paper in papers:
        paper.status = PaperStatus.INDEXED
        paper.updated_at = datetime.now(UTC)
        index_store[paper.paper_id] = paper
    for item in index_queue:
        if item["queue_id"] == queue_id:
            item["status"] = "completed"
            item["processed"] = len(papers)
            break


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/index/paper")
async def index_paper(paper: PaperDocument, actor_id: str = "SYS", actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "index:manage")
    paper.status = PaperStatus.INDEXED
    paper.updated_at = datetime.now(UTC)
    index_store[paper.paper_id] = paper
    _audit(actor_id, actor_role, "index.paper", paper.paper_id)
    return {"status": "indexed", "paper_id": paper.paper_id, "index_size": len(index_store)}


@app.post("/index/bulk")
async def bulk_index(request: BulkIndexRequest) -> dict:
    _assert_permission(request.actor_role, "index:manage")
    for paper in request.papers:
        paper.status = PaperStatus.INDEXED
        paper.updated_at = datetime.now(UTC)
        index_store[paper.paper_id] = paper
    _audit(request.actor_id, request.actor_role, "index.bulk", str(len(request.papers)))
    return {"status": "indexed", "count": len(request.papers), "index_size": len(index_store)}


@app.post("/index/queue")
async def queue_bulk_index(request: BulkIndexRequest, background_tasks: BackgroundTasks) -> dict:
    _assert_permission(request.actor_role, "index:manage")
    queue_id = f"Q-{uuid4().hex[:8].upper()}"
    index_queue.append({"queue_id": queue_id, "status": "queued", "requested": len(request.papers), "processed": 0})
    background_tasks.add_task(_async_apply_bulk, queue_id, request.papers)
    _audit(request.actor_id, request.actor_role, "index.queue", queue_id, {"requested": len(request.papers)})
    return {"queue_id": queue_id, "status": "queued", "requested": len(request.papers)}


@app.get("/index/queue/{queue_id}")
async def queue_status(queue_id: str) -> dict:
    for item in index_queue:
        if item["queue_id"] == queue_id:
            return item
    raise HTTPException(status_code=404, detail="Queue item not found")


@app.post("/search")
async def search(request: SearchRequest) -> dict:
    started = perf_counter()
    cache_key = _cache_key(request)
    cached = search_cache.get(cache_key)
    if cached is not None:
        response = SearchResponse(**cached)
        response.cache_hit = True
        return response.model_dump(mode="json")

    hits = _rank(request)
    latency_ms = round((perf_counter() - started) * 1000, 2)
    response = SearchResponse(total=len(hits), latency_ms=latency_ms, hits=hits, cache_hit=False)
    search_cache.set(cache_key, response.model_dump(mode="json"))
    return response.model_dump(mode="json")


@app.post("/search/semantic")
async def semantic_search(request: SearchRequest) -> dict:
    request.mode = SearchMode.SEMANTIC
    return await search(request)


@app.post("/search/evaluate")
async def evaluate_quality(request: QualityEvalRequest) -> dict:
    ndcg = ndcg_at_k(request.ranked_ids, request.relevant_ids, k=10)
    precision = precision_at_k(request.ranked_ids, request.relevant_ids, k=10)
    report = SearchQualityReport(
        ndcg_at_10=ndcg,
        precision_at_10=precision,
        meets_ndcg_target=ndcg >= settings.ndcg_target,
        meets_precision_target=precision >= settings.precision_target,
    )
    return report.model_dump(mode="json")


@app.get("/search/cache/stats")
async def cache_stats() -> dict:
    return search_cache.stats()


@app.get("/index/stats")
async def index_stats() -> dict:
    langs = {PaperLanguage.RU.value: 0, PaperLanguage.EN.value: 0, PaperLanguage.MULTI.value: 0}
    for paper in index_store.values():
        langs[paper.language.value] = langs.get(paper.language.value, 0) + 1

    return {
        "indexed_papers": len(index_store),
        "language_distribution": langs,
        "target_search_latency_ms": settings.search_target_ms,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


def _seed() -> None:
    demo = [
        PaperDocument(
            paper_id="PPR-DEMO-001",
            title="Graph Neural Networks for Citation Recommendation",
            abstract="Hybrid graph-text model for citation-aware recommendation in large corpora.",
            keywords=["graph neural networks", "citation", "recommendation"],
            authors=[
                {"author_id": "AUTH-001", "name": "Anna Petrova", "affiliation": "MSU"},
                {"author_id": "AUTH-002", "name": "John Smith", "affiliation": "MIT"},
            ],
            source_type="journal",
            source_name="Journal of Scholarly Data",
            year=2024,
            doi="10.1000/rn.2024.001",
            language=PaperLanguage.EN,
            citations_count=48,
            references=[],
            topics=["graph mining", "recommender systems", "scientometrics"],
            status=PaperStatus.INDEXED,
            full_text="Graph neural networks provide strong performance for citation ranking.",
            summary="Hybrid graph-text model for citation-aware recommendation.",
        ),
        PaperDocument(
            paper_id="PPR-DEMO-002",
            title="Multilingual Semantic Search for Scientific Archives",
            abstract="Embeddings for Russian and English scientific retrieval.",
            keywords=["semantic search", "multilingual", "embeddings"],
            authors=[{"author_id": "AUTH-003", "name": "Irina Volkova", "affiliation": "ITMO"}],
            source_type="conference",
            source_name="AI Systems Conf",
            year=2025,
            doi="10.1000/rn.2025.002",
            language=PaperLanguage.MULTI,
            citations_count=19,
            references=[],
            topics=["semantic retrieval", "multilingual nlp"],
            status=PaperStatus.INDEXED,
            full_text="This paper compares multilingual retrieval models with hybrid sparse-dense scoring.",
            summary="Multilingual embedding benchmarks for Russian and English abstract search.",
        ),
        PaperDocument(
            paper_id="PPR-DEMO-003",
            title="Patent Trend Forecasting with Citation Dynamics",
            abstract="Breakthrough detection in patent families using citation trajectories.",
            keywords=["patents", "forecasting", "citation dynamics"],
            authors=[{"author_id": "AUTH-004", "name": "Liu Wei", "affiliation": "Tsinghua"}],
            source_type="patent",
            source_name="Global Patent Bulletin",
            year=2023,
            doi="10.1000/rn.2023.003",
            language=PaperLanguage.EN,
            citations_count=32,
            references=[],
            topics=["trend forecasting", "patent analytics"],
            status=PaperStatus.INDEXED,
            full_text="Citation dynamics provide early breakthrough signals for patent clusters.",
            summary="Forecasting model for patent breakthrough discovery.",
        ),
    ]

    for paper in demo:
        index_store[paper.paper_id] = paper


_seed()
