from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.researchnet_common import (
    PaperMetadata,
    Role,
    SearchMode,
    SearchRequest,
    Settings,
    WorkflowResult,
    sign_token,
    verify_token,
)


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8500

    ingestion_service_url: str = "http://ingestion-service:8501"
    search_service_url: str = "http://search-service:8502"
    citation_service_url: str = "http://citation-service:8503"
    recommendation_service_url: str = "http://recommendation-service:8504"
    visualization_service_url: str = "http://visualization-service:8505"
    user_service_url: str = "http://user-service:8506"
    notification_service_url: str = "http://notification-service:8507"

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 240

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="ResearchNet API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5178",
        "http://127.0.0.1:5178",
        "http://localhost:31108",
        "http://127.0.0.1:31108",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    user_id: str
    role: Role
    language: str = Field(default="ru", pattern="^(ru|en)$")


class ProcessPaperRequest(BaseModel):
    metadata: PaperMetadata
    pdf_text: str | None = None
    actor_id: str
    actor_role: Role
    subscriber_user_ids: list[str] = Field(default_factory=list)


class ProcessBatchRequest(BaseModel):
    items: list[ProcessPaperRequest] = Field(default_factory=list)


class AddSourceRequest(BaseModel):
    name: str
    source_type: str
    provider: str
    api_url: str | None = None
    update_frequency: str = "daily"
    topics: list[str] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


AuthRequest.model_rebuild()
ProcessPaperRequest.model_rebuild()
ProcessBatchRequest.model_rebuild()
AddSourceRequest.model_rebuild()


def _service_urls() -> dict[str, str]:
    return {
        "ingestion": settings.ingestion_service_url,
        "search": settings.search_service_url,
        "citation": settings.citation_service_url,
        "recommendation": settings.recommendation_service_url,
        "visualization": settings.visualization_service_url,
        "user": settings.user_service_url,
        "notification": settings.notification_service_url,
    }


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _trigger_recommendation_update(paper_id: str) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            await _post_json(
                client,
                f"{settings.recommendation_service_url}/recommendations/update/{paper_id}",
                {"actor_id": "SYS", "actor_role": "admin"},
            )
        except Exception:
            return


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {"sub": request.user_id, "role": request.role.value, "language": request.language},
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def service_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except HTTPException as exc:
                statuses[name] = {"status": "error", "detail": exc.detail}
            except httpx.HTTPError as exc:
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


@app.post("/workflow/add-source")
async def add_source(request: AddSourceRequest) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        source = await _post_json(
            client,
            f"{settings.ingestion_service_url}/sources",
            request.model_dump(mode="json"),
        )
    return source


@app.post("/workflow/process-paper")
async def process_paper(request: ProcessPaperRequest) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        ingested = await _post_json(
            client,
            f"{settings.ingestion_service_url}/papers/ingest",
            {
                "metadata": request.metadata.model_dump(mode="json"),
                "pdf_text": request.pdf_text,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )
        paper = ingested["paper"]

        indexed = await _post_json(
            client,
            f"{settings.search_service_url}/index/paper",
            paper,
        )
        citation = await _post_json(
            client,
            f"{settings.citation_service_url}/citations/build",
            {"paper": paper},
        )

        papers_payload = await _get_json(client, f"{settings.ingestion_service_url}/papers")
        graph_payload = await _get_json(client, f"{settings.citation_service_url}/citations/graph")
        visualization = await _post_json(
            client,
            f"{settings.visualization_service_url}/visualization/refresh",
            {
                "papers": papers_payload.get("items", []),
                "citation_edges": graph_payload.get("edges", []),
                "actor_role": "admin",
            },
        )

        recommendation = await _post_json(
            client,
            f"{settings.recommendation_service_url}/recommendations/update/{paper['paper_id']}",
            {"actor_id": "SYS", "actor_role": "admin"},
        )

        asyncio.create_task(_trigger_recommendation_update(paper["paper_id"]))

        notify_payload = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/new-paper",
            {
                "user_ids": request.subscriber_user_ids,
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "matched_keywords": paper.get("keywords", [])[:5],
                "actor_role": "admin",
            },
        )

    result = WorkflowResult(
        paper=paper,
        index_result=indexed,
        citation_result=citation,
        recommendation_result=recommendation,
        visualization_result=visualization,
        notification_result=notify_payload,
    )
    return result.model_dump(mode="json")


@app.post("/workflow/process-batch")
async def process_batch(request: ProcessBatchRequest) -> dict:
    if not request.items:
        return {"items": [], "count": 0}

    payload_items = []
    for item in request.items:
        payload_items.append(
            {
                "metadata": item.metadata.model_dump(mode="json"),
                "pdf_text": item.pdf_text,
                "actor_id": item.actor_id,
                "actor_role": item.actor_role.value,
            }
        )

    async with httpx.AsyncClient(timeout=50.0) as client:
        batch = await _post_json(client, f"{settings.ingestion_service_url}/papers/ingest/batch", {"items": payload_items})
        queue = await _post_json(
            client,
            f"{settings.search_service_url}/index/queue",
            {
                "papers": batch.get("items", []),
                "actor_id": "SYS",
                "actor_role": "admin",
            },
        )
    return {"ingestion": batch, "index_queue": queue}


@app.post("/search")
async def search_proxy(request: SearchRequest) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _post_json(client, f"{settings.search_service_url}/search", request.model_dump(mode="json"))


@app.post("/search/semantic")
async def semantic_search_proxy(request: SearchRequest) -> dict:
    request.mode = SearchMode.SEMANTIC
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _post_json(client, f"{settings.search_service_url}/search/semantic", request.model_dump(mode="json"))


@app.get("/dashboard/{paper_id}/{user_id}")
async def dashboard(paper_id: str, user_id: str) -> dict:
    async with httpx.AsyncClient(timeout=25.0) as client:
        paper = await _get_json(client, f"{settings.ingestion_service_url}/papers/{paper_id}")
        recommendations = await _get_json(client, f"{settings.recommendation_service_url}/recommendations/paper/{paper_id}")
        citation_graph = await _get_json(client, f"{settings.citation_service_url}/citations/graph")
        key_works = await _get_json(client, f"{settings.citation_service_url}/works/key", {"limit": 5})
        coauthors = await _get_json(client, f"{settings.visualization_service_url}/graphs/coauthors/interactive")
        trends = await _get_json(client, f"{settings.visualization_service_url}/trends/topics")
        overview = await _get_json(client, f"{settings.visualization_service_url}/dashboards/overview")
        user = await _get_json(client, f"{settings.user_service_url}/users/{user_id}")
        favorites = await _get_json(client, f"{settings.user_service_url}/users/{user_id}/favorites")
        subscriptions = await _get_json(client, f"{settings.user_service_url}/subscriptions/{user_id}")
        notifications = await _get_json(client, f"{settings.notification_service_url}/notify/history", {"user_id": user_id})

        search_quality = await _post_json(
            client,
            f"{settings.search_service_url}/search/evaluate",
            {
                "ranked_ids": [item["paper_id"] for item in recommendations.get("items", [])],
                "relevant_ids": [item["paper_id"] for item in favorites.get("items", [])],
            },
        )

    return {
        "paper": paper,
        "recommendations": recommendations,
        "citation_graph": citation_graph,
        "key_works": key_works,
        "coauthors": coauthors,
        "trends": trends,
        "overview": overview,
        "user": user,
        "favorites": favorites,
        "subscriptions": subscriptions,
        "notifications": notifications,
        "search_quality": search_quality,
    }
