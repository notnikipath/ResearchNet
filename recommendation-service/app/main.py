from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.researchnet_common import (
    ExpertRecommendation,
    PaperDocument,
    PaperStatus,
    RecommendationItem,
    RecommendationRequest,
    Role,
    Settings,
    TopicCluster,
    TrendForecast,
    build_audit_event,
    build_personal_digest,
    cluster_topics,
    collaborative_score,
    forecast_breakthrough,
    has_permission,
    jaccard_similarity,
    precision_at_k,
)

settings = Settings(service_name="recommendation-service", service_port=8504)
app = FastAPI(title="ResearchNet Recommendation Service", version="1.0.0")


class RecommendationUpdatePayload(BaseModel):
    papers: list[PaperDocument] = Field(default_factory=list)
    user_favorites: dict[str, list[str]] = Field(default_factory=dict)
    actor_id: str = "SYS"
    actor_role: Role = Role.ADMIN


class FavoriteIngestRequest(BaseModel):
    user_id: str
    paper_id: str


RecommendationUpdatePayload.model_rebuild()
FavoriteIngestRequest.model_rebuild()


papers: dict[str, PaperDocument] = {}
user_favorites: dict[str, list[str]] = {
    "USR-001": ["PPR-DEMO-001", "PPR-DEMO-002"],
    "USR-002": ["PPR-DEMO-001", "PPR-DEMO-003"],
}
recommendations: dict[str, list[RecommendationItem]] = {}
audit_log: list[dict] = []

experts = [
    {"expert_id": "AUTH-001", "name": "Anna Petrova", "topic": "graph mining", "h_index": 22, "top_papers": ["PPR-DEMO-001"]},
    {"expert_id": "AUTH-003", "name": "Irina Volkova", "topic": "semantic retrieval", "h_index": 17, "top_papers": ["PPR-DEMO-002"]},
    {"expert_id": "AUTH-004", "name": "Liu Wei", "topic": "trend forecasting", "h_index": 19, "top_papers": ["PPR-DEMO-003"]},
]


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="recommendation",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _content_score(source: PaperDocument, candidate: PaperDocument) -> tuple[float, list[str]]:
    shared_topics = sorted(set(source.topics) & set(candidate.topics))
    text_left = f"{source.title} {source.abstract} {' '.join(source.keywords)}"
    text_right = f"{candidate.title} {candidate.abstract} {' '.join(candidate.keywords)}"
    score = jaccard_similarity(text_left, text_right)
    topic_bonus = min(len(shared_topics) * 0.08, 0.32)
    citation_bonus = min(candidate.citations_count / 300, 0.12)
    return round(score * 0.7 + topic_bonus + citation_bonus, 6), shared_topics


def _rank_for_paper(paper_id: str, limit: int = 10) -> list[RecommendationItem]:
    source = papers.get(paper_id)
    if source is None:
        return []

    ranked: list[RecommendationItem] = []
    for candidate in papers.values():
        if candidate.paper_id == paper_id:
            continue
        content, shared_topics = _content_score(source, candidate)
        collab = collaborative_score(paper_id, user_favorites, candidate.paper_id)
        blended = round(content * 0.75 + collab * 0.25, 6)
        if blended <= 0:
            continue
        ranked.append(
            RecommendationItem(
                paper_id=candidate.paper_id,
                score=blended,
                reason="content + collaborative",
                shared_topics=shared_topics,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:limit]


def _topic_clusters() -> list[TopicCluster]:
    raw = cluster_topics([paper.model_dump(mode="json") for paper in papers.values()])
    return [TopicCluster(**item) for item in raw]


def _trend_forecasts() -> list[TrendForecast]:
    topic_series: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for paper in papers.values():
        for topic in paper.topics[:3]:
            topic_series[topic.lower()][paper.year] += 1

    items = []
    for topic, series in topic_series.items():
        forecast = forecast_breakthrough(dict(series))
        items.append(
            TrendForecast(
                topic=topic,
                slope=forecast["slope"],
                growth_score=forecast["growth_score"],
                breakthrough_probability=forecast["breakthrough_probability"],
            )
        )
    items.sort(key=lambda item: item.breakthrough_probability, reverse=True)
    return items


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/recommendations/update/{paper_id}")
async def update_for_paper(paper_id: str, actor_id: str = "SYS", actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "recommendation:manage")
    ranked = _rank_for_paper(paper_id, limit=10)
    recommendations[paper_id] = ranked
    paper = papers.get(paper_id)
    if paper is not None:
        paper.status = PaperStatus.RECOMMENDATIONS_UPDATED
        paper.updated_at = datetime.now(UTC)
    _audit(actor_id, actor_role, "recommendation.update", paper_id, {"count": len(ranked)})
    return {"paper_id": paper_id, "updated": len(ranked)}


@app.post("/recommendations/rebuild")
async def rebuild(payload: RecommendationUpdatePayload) -> dict:
    _assert_permission(payload.actor_role, "recommendation:manage")
    for paper in payload.papers:
        papers[paper.paper_id] = paper
    if payload.user_favorites:
        for user_id, favorite_list in payload.user_favorites.items():
            user_favorites[user_id] = list(dict.fromkeys(favorite_list))

    updated = 0
    for paper_id in list(papers.keys()):
        recommendations[paper_id] = _rank_for_paper(paper_id, limit=10)
        updated += 1

    _audit(payload.actor_id, payload.actor_role, "recommendation.rebuild", str(updated))
    return {"status": "ok", "papers_updated": updated}


@app.post("/recommendations/similar")
async def similar(request: RecommendationRequest) -> dict:
    if request.paper_id not in papers:
        raise HTTPException(status_code=404, detail="Paper not found")
    ranked = recommendations.get(request.paper_id) or _rank_for_paper(request.paper_id, request.limit)
    return {"paper_id": request.paper_id, "items": [item.model_dump(mode="json") for item in ranked[: request.limit]]}


@app.get("/recommendations/paper/{paper_id}")
async def paper_recommendations(paper_id: str, limit: int = 10) -> dict:
    if paper_id not in papers:
        raise HTTPException(status_code=404, detail="Paper not found")
    ranked = recommendations.get(paper_id) or _rank_for_paper(paper_id, limit)
    return {"paper_id": paper_id, "items": [item.model_dump(mode="json") for item in ranked[:limit]], "count": min(limit, len(ranked))}


@app.post("/interactions/favorite")
async def ingest_favorite(event: FavoriteIngestRequest) -> dict:
    user_favorites.setdefault(event.user_id, [])
    if event.paper_id not in user_favorites[event.user_id]:
        user_favorites[event.user_id].append(event.paper_id)
    return {"status": "ok", "favorites": user_favorites[event.user_id]}


@app.get("/recommendations/experts")
async def recommend_experts(topic: str, limit: int = 5) -> dict:
    topic_norm = topic.lower().strip()
    items: list[ExpertRecommendation] = []
    for expert in experts:
        match = 1.0 if topic_norm and topic_norm in expert["topic"] else 0.45
        score = round(min(1.0, match * 0.7 + expert["h_index"] / 100), 4)
        items.append(
            ExpertRecommendation(
                expert_id=expert["expert_id"],
                name=expert["name"],
                topic=expert["topic"],
                score=score,
                h_index=expert["h_index"],
                top_papers=expert["top_papers"],
            )
        )
    items.sort(key=lambda item: item.score, reverse=True)
    return {"items": [item.model_dump(mode="json") for item in items[:limit]], "count": min(limit, len(items))}


@app.get("/clusters/topics")
async def topic_clusters() -> dict:
    clusters = _topic_clusters()
    return {"items": [cluster.model_dump(mode="json") for cluster in clusters], "count": len(clusters)}


@app.get("/trends/forecast")
async def trend_forecast() -> dict:
    items = _trend_forecasts()
    return {"items": [item.model_dump(mode="json") for item in items], "count": len(items)}


@app.get("/quality/precision")
async def quality_precision() -> dict:
    if not recommendations:
        for paper_id in papers:
            recommendations[paper_id] = _rank_for_paper(paper_id, 10)

    sample_paper = "PPR-DEMO-001"
    ranked = [item.paper_id for item in recommendations.get(sample_paper, [])]
    relevant = ["PPR-DEMO-002", "PPR-DEMO-003"]
    score = precision_at_k(ranked, relevant, k=10)
    return {
        "precision_at_10": score,
        "target": settings.precision_target,
        "meets_target": score >= settings.precision_target,
    }


@app.get("/digests/{user_id}")
async def personalized_digest(user_id: str) -> dict:
    favorites = user_favorites.get(user_id, [])
    focus_topics: list[str] = []
    selected: list[dict] = []

    for paper_id in favorites[:5]:
        paper = papers.get(paper_id)
        if not paper:
            continue
        focus_topics.extend(paper.topics[:2])
        selected.append(paper.model_dump(mode="json"))

    digest = build_personal_digest(user_name=user_id, topics=focus_topics, papers=selected)
    return {"user_id": user_id, "digest": digest, "paper_count": len(selected)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


def _seed() -> None:
    seeded = [
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
            references=[],
            topics=["graph mining", "recommender systems", "scientometrics"],
            status=PaperStatus.RECOMMENDATIONS_UPDATED,
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
            status=PaperStatus.RECOMMENDATIONS_UPDATED,
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
            references=[],
            topics=["trend forecasting", "patent analytics"],
            status=PaperStatus.RECOMMENDATIONS_UPDATED,
            full_text="...",
            summary="...",
        ),
    ]
    for paper in seeded:
        papers[paper.paper_id] = paper

    for paper_id in papers:
        recommendations[paper_id] = _rank_for_paper(paper_id, limit=10)


_seed()
