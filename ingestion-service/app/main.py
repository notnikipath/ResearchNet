from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.researchnet_common import (
    PaperBatchRequest,
    PaperDocument,
    PaperIngestRequest,
    PaperMetadata,
    PaperStatus,
    ProviderType,
    Role,
    ScheduleFrequency,
    Settings,
    SourceConfig,
    SourceSyncRequest,
    SourceType,
    build_audit_event,
    extract_keywords,
    has_permission,
    indexing_rate_per_hour,
    parallel_pdf_plan,
    summarize_text,
)

settings = Settings(service_name="ingestion-service", service_port=8501)
app = FastAPI(title="ResearchNet Ingestion Service", version="1.0.0")


class ProviderFetchRequest(BaseModel):
    provider: ProviderType
    query: str
    source_type: SourceType = SourceType.JOURNAL
    year: int = Field(default=datetime.now(UTC).year, ge=1900, le=2100)


class SourceCreateRequest(BaseModel):
    name: str
    source_type: SourceType
    provider: ProviderType = ProviderType.MANUAL
    api_url: str | None = None
    update_frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    topics: list[str] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


sources: dict[str, SourceConfig] = {
    "SRC-CROSSREF": SourceConfig(
        source_id="SRC-CROSSREF",
        name="CrossRef Journals",
        source_type=SourceType.JOURNAL,
        provider=ProviderType.CROSSREF,
        api_url="https://api.crossref.org/works",
        update_frequency=ScheduleFrequency.HOURLY,
        topics=["machine learning", "nlp"],
    ),
    "SRC-PUBMED": SourceConfig(
        source_id="SRC-PUBMED",
        name="PubMed",
        source_type=SourceType.JOURNAL,
        provider=ProviderType.PUBMED,
        api_url="https://pubmed.ncbi.nlm.nih.gov",
        update_frequency=ScheduleFrequency.DAILY,
        topics=["bioinformatics", "genomics"],
    ),
    "SRC-IEEE": SourceConfig(
        source_id="SRC-IEEE",
        name="IEEE Conferences",
        source_type=SourceType.CONFERENCE,
        provider=ProviderType.IEEE,
        api_url="https://ieeexploreapi.ieee.org",
        update_frequency=ScheduleFrequency.DAILY,
        topics=["computer vision", "robotics"],
    ),
}

papers: dict[str, PaperDocument] = {}
audit_log: list[dict] = []
processed_count = 0
started_at = datetime.now(UTC)


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="ingestion",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _extract_references(pdf_text: str) -> list[str]:
    refs = []
    for line in pdf_text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.lower().startswith("ref:") or candidate.lower().startswith("reference:"):
            refs.append(candidate.split(":", maxsplit=1)[1].strip())
    return refs[:80]


def _build_document(request: PaperIngestRequest) -> PaperDocument:
    metadata = request.metadata
    full_text = request.pdf_text or metadata.abstract
    generated_keywords = extract_keywords(metadata.title, metadata.abstract)
    all_keywords = sorted(set(metadata.keywords + generated_keywords))
    summary = summarize_text(metadata.title, metadata.abstract, full_text)

    references = metadata.references
    if not references:
        for idx, ref_title in enumerate(_extract_references(full_text), start=1):
            references.append(
                {
                    "ref_id": f"{metadata.paper_id}-REF-{idx}",
                    "title": ref_title,
                    "authors": [],
                    "year": None,
                    "doi": None,
                    "paper_id": None,
                }
            )

    return PaperDocument(
        paper_id=metadata.paper_id,
        title=metadata.title,
        abstract=metadata.abstract,
        keywords=all_keywords,
        authors=metadata.authors,
        source_type=metadata.source_type,
        source_name=metadata.source_name,
        year=metadata.year,
        published_at=metadata.published_at,
        doi=metadata.doi,
        language=metadata.language,
        pdf_url=metadata.pdf_url,
        citations_count=metadata.citations_count,
        references=references,
        topics=metadata.topics or all_keywords[:6],
        status=PaperStatus.COLLECTED,
        full_text=full_text,
        summary=summary,
        updated_at=datetime.now(UTC),
    )


def _provider_stub(request: ProviderFetchRequest) -> PaperMetadata:
    seed_title = request.query.strip() or "Untitled scientific work"
    source_name = {
        ProviderType.CROSSREF: "CrossRef Indexed Journal",
        ProviderType.PUBMED: "PubMed Open Archive",
        ProviderType.IEEE: "IEEE Conference Proceedings",
        ProviderType.ARXIV: "arXiv",
        ProviderType.BIORXIV: "bioRxiv",
        ProviderType.MANUAL: "Manual Source",
    }[request.provider]

    return PaperMetadata(
        paper_id=f"PPR-{uuid4().hex[:10].upper()}",
        title=seed_title,
        abstract=f"This paper studies {seed_title.lower()} with reproducible methods and multilingual annotation support.",
        keywords=extract_keywords(seed_title, seed_title),
        authors=[],
        source_type=request.source_type,
        source_name=source_name,
        year=request.year,
        doi=f"10.1234/{uuid4().hex[:8]}",
        topics=extract_keywords(seed_title, seed_title, top_k=4),
        is_preprint=request.source_type == SourceType.PREPRINT,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/sources")
async def list_sources(active_only: bool = False) -> dict:
    items = [
        source.model_dump(mode="json")
        for source in sources.values()
        if not active_only or source.is_active
    ]
    return {"items": items, "count": len(items)}


@app.post("/sources")
async def create_source(request: SourceCreateRequest) -> dict:
    if request.actor_role == Role.RESEARCHER:
        _assert_permission(request.actor_role, "source:manage:self")
    else:
        _assert_permission(request.actor_role, "source:manage")

    source = SourceConfig(
        source_id=f"SRC-{uuid4().hex[:8].upper()}",
        name=request.name,
        source_type=request.source_type,
        provider=request.provider,
        api_url=request.api_url,
        update_frequency=request.update_frequency,
        topics=request.topics,
    )
    sources[source.source_id] = source
    _audit(request.actor_id, request.actor_role, "source.create", source.source_id)
    return source.model_dump(mode="json")


@app.post("/sources/sync")
async def sync_source(request: SourceSyncRequest) -> dict:
    if request.actor_role == Role.RESEARCHER:
        _assert_permission(request.actor_role, "source:manage:self")
    else:
        _assert_permission(request.actor_role, "source:manage")

    source = sources.get(request.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    source.last_sync_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "source.sync", source.source_id, {"force": request.force})
    return {"status": "ok", "source": source.model_dump(mode="json")}


@app.post("/providers/fetch")
async def provider_fetch(request: ProviderFetchRequest) -> dict:
    metadata = _provider_stub(request)
    return metadata.model_dump(mode="json")


@app.post("/papers/ingest")
async def ingest_paper(request: PaperIngestRequest) -> dict:
    global processed_count
    _assert_permission(request.actor_role, "paper:ingest")

    started = perf_counter()
    document = _build_document(request)
    papers[document.paper_id] = document
    processed_count += 1

    _audit(request.actor_id, request.actor_role, "paper.ingest", document.paper_id)
    return {
        "paper": document.model_dump(mode="json"),
        "processing_ms": round((perf_counter() - started) * 1000, 2),
    }


@app.post("/papers/ingest/batch")
async def ingest_batch(request: PaperBatchRequest) -> dict:
    global processed_count
    if not request.items:
        return {"items": [], "count": 0, "parallel_plan": parallel_pdf_plan(0, 0)}

    role = request.items[0].actor_role
    _assert_permission(role, "paper:ingest")

    avg_pages = 12
    plan = parallel_pdf_plan(len(request.items), avg_pages)
    items = []
    for item in request.items:
        document = _build_document(item)
        document.status = PaperStatus.COLLECTED
        papers[document.paper_id] = document
        processed_count += 1
        items.append(document.model_dump(mode="json"))

    _audit(request.items[0].actor_id, role, "paper.ingest.batch", str(len(items)), {"parallel_plan": plan})
    return {"items": items, "count": len(items), "parallel_plan": plan}


@app.get("/papers")
async def list_papers(year: int | None = None, source_type: SourceType | None = None) -> dict:
    result = []
    for paper in papers.values():
        if year and paper.year != year:
            continue
        if source_type and paper.source_type != source_type:
            continue
        result.append(paper.model_dump(mode="json"))
    result.sort(key=lambda item: item["year"], reverse=True)
    return {"items": result, "count": len(result)}


@app.get("/papers/{paper_id}")
async def get_paper(paper_id: str) -> dict:
    paper = papers.get(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper.model_dump(mode="json")


@app.get("/stats")
async def stats() -> dict:
    elapsed_minutes = max((datetime.now(UTC) - started_at).total_seconds() / 60, 0.0001)
    return {
        "papers_total": len(papers),
        "sources_total": len(sources),
        "indexing_rate_per_hour": indexing_rate_per_hour(processed_count, elapsed_minutes),
        "target_indexing_per_hour": settings.indexing_target_per_hour,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


def _seed() -> None:
    demo_papers = [
        PaperIngestRequest(
            metadata=PaperMetadata(
                paper_id="PPR-DEMO-001",
                title="Graph Neural Networks for Citation Recommendation",
                abstract="We present a hybrid graph-text model for citation-aware recommendation in large corpora.",
                keywords=["graph neural networks", "citation", "recommendation"],
                authors=[
                    {"author_id": "AUTH-001", "name": "Anna Petrova", "affiliation": "MSU", "orcid_id": "0000-0001-001"},
                    {"author_id": "AUTH-002", "name": "John Smith", "affiliation": "MIT", "orcid_id": "0000-0002-002"},
                ],
                source_type=SourceType.JOURNAL,
                source_name="Journal of Scholarly Data",
                year=2024,
                doi="10.1000/rn.2024.001",
                citations_count=48,
                topics=["graph mining", "recommender systems", "scientometrics"],
            ),
            pdf_text="Introduction... REF: Foundational citation graph model. REF: Embedding based retrieval.",
            actor_id="SYS",
            actor_role=Role.ADMIN,
        ),
        PaperIngestRequest(
            metadata=PaperMetadata(
                paper_id="PPR-DEMO-002",
                title="Multilingual Semantic Search for Scientific Archives",
                abstract="This work benchmarks multilingual embeddings for Russian and English abstract retrieval.",
                keywords=["semantic search", "multilingual", "embeddings"],
                authors=[
                    {"author_id": "AUTH-003", "name": "Irina Volkova", "affiliation": "ITMO", "orcid_id": "0000-0003-003"},
                ],
                source_type=SourceType.CONFERENCE,
                source_name="AI Systems Conf",
                year=2025,
                doi="10.1000/rn.2025.002",
                citations_count=19,
                topics=["semantic retrieval", "multilingual nlp"],
            ),
            pdf_text="Abstract... REF: Cross-lingual ranking benchmarks.",
            actor_id="SYS",
            actor_role=Role.ADMIN,
        ),
        PaperIngestRequest(
            metadata=PaperMetadata(
                paper_id="PPR-DEMO-003",
                title="Patent Trend Forecasting with Citation Dynamics",
                abstract="A forecasting approach to detect breakthrough patent families from citation trajectories.",
                keywords=["patents", "forecasting", "citation dynamics"],
                authors=[
                    {"author_id": "AUTH-004", "name": "Liu Wei", "affiliation": "Tsinghua", "orcid_id": "0000-0004-004"},
                ],
                source_type=SourceType.PATENT,
                source_name="Global Patent Bulletin",
                year=2023,
                doi="10.1000/rn.2023.003",
                citations_count=32,
                topics=["trend forecasting", "patent analytics"],
            ),
            pdf_text="Methods and data sections... REF: Time-series breakthrough detection.",
            actor_id="SYS",
            actor_role=Role.ADMIN,
        ),
    ]

    for item in demo_papers:
        paper = _build_document(item)
        papers[paper.paper_id] = paper


_seed()
