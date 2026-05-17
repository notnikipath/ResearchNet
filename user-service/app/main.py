from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.researchnet_common import (
    PaperDocument,
    Role,
    ScheduleFrequency,
    Settings,
    Subscription,
    SubscriptionCreateRequest,
    UserProfile,
    build_audit_event,
    export_bibtex,
    export_ris,
    has_permission,
)

settings = Settings(service_name="user-service", service_port=8506)
app = FastAPI(title="ResearchNet User Service", version="1.0.0")


class UserCreateRequest(BaseModel):
    user_id: str
    name: str
    email: str
    role: Role = Role.READER
    affiliation: str | None = None
    research_interests: list[str] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class OrcidLinkRequest(BaseModel):
    orcid_id: str
    actor_id: str
    actor_role: Role


class FavoriteRequest(BaseModel):
    actor_id: str
    actor_role: Role


UserCreateRequest.model_rebuild()
OrcidLinkRequest.model_rebuild()
FavoriteRequest.model_rebuild()


users: dict[str, UserProfile] = {
    "USR-001": UserProfile(
        user_id="USR-001",
        name="Nikolai Ivanov",
        email="nikolai@example.org",
        role=Role.RESEARCHER,
        affiliation="ITMO",
        research_interests=["graph mining", "scientometrics"],
        favorites=["PPR-DEMO-001", "PPR-DEMO-002"],
    ),
    "USR-002": UserProfile(
        user_id="USR-002",
        name="Emily Clark",
        email="emily@example.org",
        role=Role.READER,
        affiliation="University of Toronto",
        research_interests=["semantic retrieval"],
        favorites=["PPR-DEMO-003"],
    ),
}

subscriptions: dict[str, list[Subscription]] = {
    "USR-001": [
        Subscription(
            subscription_id="SUB-001",
            user_id="USR-001",
            keywords=["citation graph", "recommender systems"],
            author_ids=["AUTH-001"],
            journal_filters=["Journal of Scholarly Data"],
            frequency=ScheduleFrequency.DAILY,
        )
    ]
}

paper_catalog: dict[str, PaperDocument] = {
    "PPR-DEMO-001": PaperDocument(
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
        full_text="...",
        summary="...",
    ),
    "PPR-DEMO-002": PaperDocument(
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
        full_text="...",
        summary="...",
    ),
    "PPR-DEMO-003": PaperDocument(
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
        full_text="...",
        summary="...",
    ),
}

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
            object_type="user",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/users")
async def list_users() -> dict:
    items = [user.model_dump(mode="json") for user in users.values()]
    return {"items": items, "count": len(items)}


@app.post("/users")
async def create_user(request: UserCreateRequest) -> dict:
    _assert_permission(request.actor_role, "user:manage")
    if request.user_id in users:
        raise HTTPException(status_code=409, detail="User already exists")

    profile = UserProfile(
        user_id=request.user_id,
        name=request.name,
        email=request.email,
        role=request.role,
        affiliation=request.affiliation,
        research_interests=request.research_interests,
        favorites=[],
    )
    users[profile.user_id] = profile
    _audit(request.actor_id, request.actor_role, "user.create", profile.user_id)
    return profile.model_dump(mode="json")


@app.get("/users/{user_id}")
async def get_user(user_id: str) -> dict:
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.model_dump(mode="json")


@app.post("/users/{user_id}/orcid/link")
async def link_orcid(user_id: str, request: OrcidLinkRequest) -> dict:
    if request.actor_role not in {Role.RESEARCHER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.orcid_id = request.orcid_id
    _audit(request.actor_id, request.actor_role, "user.orcid.link", user_id, {"orcid": request.orcid_id})
    return user.model_dump(mode="json")


@app.post("/users/{user_id}/favorites/{paper_id}")
async def add_favorite(user_id: str, paper_id: str, request: FavoriteRequest) -> dict:
    _assert_permission(request.actor_role, "favorites:write")
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if paper_id not in paper_catalog:
        # Gateway can submit favorites before metadata sync reaches user-service.
        paper_catalog[paper_id] = PaperDocument(
            paper_id=paper_id,
            title=f"Imported paper {paper_id}",
            abstract="Metadata is pending synchronization from ingestion-service.",
            keywords=["pending-sync"],
            authors=[],
            source_type="preprint",
            source_name="Unknown source",
            year=2026,
            citations_count=0,
            references=[],
            topics=["pending-sync"],
            full_text="",
            summary="Pending metadata synchronization.",
        )

    if paper_id not in user.favorites:
        user.favorites.append(paper_id)
    _audit(request.actor_id, request.actor_role, "user.favorite.add", user_id, {"paper_id": paper_id})
    return {"user_id": user_id, "favorites": user.favorites}


@app.get("/users/{user_id}/favorites")
async def list_favorites(user_id: str) -> dict:
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    items = []
    for paper_id in user.favorites:
        paper = paper_catalog.get(paper_id)
        if paper:
            items.append(paper.model_dump(mode="json"))
    return {"user_id": user_id, "items": items, "count": len(items)}


@app.post("/subscriptions")
async def create_subscription(request: SubscriptionCreateRequest, actor_id: str = "SYS", actor_role: Role = Role.RESEARCHER) -> dict:
    _assert_permission(actor_role, "subscription:write")
    if request.user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    subscription = Subscription(
        subscription_id=f"SUB-{uuid4().hex[:8].upper()}",
        user_id=request.user_id,
        keywords=request.keywords,
        author_ids=request.author_ids,
        journal_filters=request.journal_filters,
        frequency=request.frequency,
    )
    subscriptions.setdefault(request.user_id, []).append(subscription)
    _audit(actor_id, actor_role, "subscription.create", subscription.subscription_id)
    return subscription.model_dump(mode="json")


@app.get("/subscriptions/{user_id}")
async def list_subscriptions(user_id: str) -> dict:
    items = [item.model_dump(mode="json") for item in subscriptions.get(user_id, []) if item.is_active]
    return {"user_id": user_id, "items": items, "count": len(items)}


@app.get("/exports/{user_id}")
async def export_favorites(user_id: str, format: str = "bibtex") -> dict:
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    rows: list[str] = []
    for paper_id in user.favorites:
        paper = paper_catalog.get(paper_id)
        if not paper:
            continue
        payload = paper.model_dump(mode="json")
        if format.lower() == "ris":
            rows.append(export_ris(payload))
        else:
            rows.append(export_bibtex(payload))

    return {
        "user_id": user_id,
        "format": format.lower(),
        "items": rows,
        "count": len(rows),
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
