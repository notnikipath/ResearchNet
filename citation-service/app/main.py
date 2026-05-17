from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.researchnet_common import (
    AuthorCitationMetrics,
    CitationBuildRequest,
    CitationEdge,
    CitationGraphSnapshot,
    JournalMetrics,
    KeyPaper,
    PaperDocument,
    PaperStatus,
    Role,
    Settings,
    build_audit_event,
    h_index,
    has_permission,
    i10_index,
    impact_factor,
    key_paper_score,
    shard_topics,
)

settings = Settings(service_name="citation-service", service_port=8503)
app = FastAPI(title="ResearchNet Citation Service", version="1.0.0")


class ManualEdgeRequest(BaseModel):
    edge: CitationEdge
    actor_id: str
    actor_role: Role


papers: dict[str, PaperDocument] = {}
edges: list[CitationEdge] = []
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
            object_type="citation",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _reference_to_paper_id(reference_title: str) -> str:
    for paper_id, paper in papers.items():
        if reference_title and reference_title.lower() in paper.title.lower():
            return paper_id
    return f"EXT-{abs(hash(reference_title)) % 100000}"


def _rebuild_edges_for_paper(paper: PaperDocument) -> list[CitationEdge]:
    new_edges = [edge for edge in edges if edge.citing_paper_id != paper.paper_id]
    created: list[CitationEdge] = []
    for ref in paper.references:
        cited_paper_id = ref.paper_id or _reference_to_paper_id(ref.title)
        edge = CitationEdge(
            citing_paper_id=paper.paper_id,
            cited_paper_id=cited_paper_id,
            weight=1,
            year=paper.year,
        )
        created.append(edge)
        new_edges.append(edge)
    edges.clear()
    edges.extend(new_edges)
    return created


def _pagerank_like() -> dict[str, float]:
    inbound: dict[str, int] = defaultdict(int)
    for edge in edges:
        inbound[edge.cited_paper_id] += edge.weight
    max_count = max(inbound.values()) if inbound else 1
    return {paper_id: inbound.get(paper_id, 0) / max_count for paper_id in papers}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/citations/build")
async def build_for_paper(request: CitationBuildRequest, actor_id: str = "SYS", actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "citation:manage")
    paper = request.paper
    paper.status = PaperStatus.CITATION_ANALYZED
    paper.updated_at = datetime.now(UTC)
    papers[paper.paper_id] = paper
    created = _rebuild_edges_for_paper(paper)
    _audit(actor_id, actor_role, "citation.build", paper.paper_id, {"edges": len(created)})
    return {
        "paper_id": paper.paper_id,
        "edges_created": len(created),
        "graph_size": len(edges),
    }


@app.post("/citations/edge")
async def add_edge(request: ManualEdgeRequest) -> dict:
    _assert_permission(request.actor_role, "citation:manage")
    edges.append(request.edge)
    _audit(request.actor_id, request.actor_role, "citation.edge.create", request.edge.citing_paper_id)
    return {"status": "ok", "graph_size": len(edges)}


@app.get("/citations/graph")
async def graph_snapshot() -> dict:
    snapshot = CitationGraphSnapshot(
        nodes=sorted(set(list(papers.keys()) + [edge.cited_paper_id for edge in edges])),
        edges=edges,
    )
    return snapshot.model_dump(mode="json")


@app.get("/citations/graph/shards")
async def graph_shards() -> dict:
    docs = [paper.model_dump(mode="json") for paper in papers.values()]
    return {
        "shards": shard_topics(docs, shards=4),
        "strategy": "topic-hash",
    }


@app.get("/metrics/author/{author_id}")
async def author_metrics(author_id: str) -> dict:
    _assert_permission(Role.RESEARCHER, "citation:read")
    author_papers = [paper for paper in papers.values() if any(author.author_id == author_id for author in paper.authors)]
    citation_counts = [paper.citations_count for paper in author_papers]
    metrics = AuthorCitationMetrics(
        author_id=author_id,
        papers=len(author_papers),
        citations=sum(citation_counts),
        h_index=h_index(citation_counts),
        i10_index=i10_index(citation_counts),
    )
    return metrics.model_dump(mode="json")


@app.get("/metrics/journal/{journal}")
async def journal_metrics(journal: str) -> dict:
    _assert_permission(Role.RESEARCHER, "citation:read")
    current_year = datetime.now(UTC).year
    window_years = {current_year - 1, current_year - 2}

    citable = [paper for paper in papers.values() if paper.source_name.lower() == journal.lower() and paper.year in window_years]
    citations_in_window = sum(paper.citations_count for paper in citable)
    metrics = JournalMetrics(
        journal=journal,
        year=current_year,
        impact_factor=impact_factor(citations_in_window, len(citable)),
        citations_in_window=citations_in_window,
        citable_items=len(citable),
    )
    return metrics.model_dump(mode="json")


@app.get("/works/key")
async def key_works(limit: int = 10) -> dict:
    _assert_permission(Role.RESEARCHER, "citation:read")
    centrality = _pagerank_like()
    current_year = datetime.now(UTC).year

    items: list[KeyPaper] = []
    for paper in papers.values():
        score = key_paper_score(
            citations=paper.citations_count,
            recency_years=max(current_year - paper.year, 0),
            pagerank_like=centrality.get(paper.paper_id, 0.0),
        )
        items.append(
            KeyPaper(
                paper_id=paper.paper_id,
                title=paper.title,
                score=score,
                reason="citation volume + recency + graph centrality",
            )
        )

    items.sort(key=lambda item: item.score, reverse=True)
    return {"items": [item.model_dump(mode="json") for item in items[:limit]], "count": min(limit, len(items))}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


def _seed() -> None:
    initial = [
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
            citations_count=48,
            references=[
                {"ref_id": "R1", "title": "Multilingual Semantic Search for Scientific Archives", "paper_id": "PPR-DEMO-002"},
                {"ref_id": "R2", "title": "Patent Trend Forecasting with Citation Dynamics", "paper_id": "PPR-DEMO-003"},
            ],
            topics=["graph mining", "recommender systems", "scientometrics"],
            status=PaperStatus.CITATION_ANALYZED,
            full_text="...",
            summary="...",
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
            citations_count=19,
            references=[],
            topics=["semantic retrieval", "multilingual nlp"],
            status=PaperStatus.CITATION_ANALYZED,
            full_text="...",
            summary="...",
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
            citations_count=32,
            references=[{"ref_id": "R3", "title": "Graph Neural Networks for Citation Recommendation", "paper_id": "PPR-DEMO-001"}],
            topics=["trend forecasting", "patent analytics"],
            status=PaperStatus.CITATION_ANALYZED,
            full_text="...",
            summary="...",
        ),
    ]

    for paper in initial:
        papers[paper.paper_id] = paper

    for paper in initial:
        _rebuild_edges_for_paper(paper)


_seed()
