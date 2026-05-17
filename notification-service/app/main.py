from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.researchnet_common import (
    AlertType,
    NotificationChannel,
    NotificationPayload,
    Role,
    Settings,
    has_permission,
)

settings = Settings(service_name="notification-service", service_port=8507)
app = FastAPI(title="ResearchNet Notification Service", version="1.0.0")

messages: list[NotificationPayload] = []


class SendRequest(BaseModel):
    user_id: str
    channel: NotificationChannel = NotificationChannel.IN_APP
    subject: str
    body: str
    alert_type: AlertType = AlertType.NEW_PAPER
    actor_role: Role


class NewPaperRequest(BaseModel):
    user_ids: list[str] = Field(default_factory=list)
    paper_id: str
    title: str
    matched_keywords: list[str] = Field(default_factory=list)
    actor_role: Role


class CitationRequest(BaseModel):
    user_id: str
    paper_id: str
    citation_by: str
    actor_role: Role


class DigestRequest(BaseModel):
    user_id: str
    digest: str
    actor_role: Role


SendRequest.model_rebuild()
NewPaperRequest.model_rebuild()
CitationRequest.model_rebuild()
DigestRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _queue(payload: NotificationPayload) -> dict[str, Any]:
    messages.append(payload)
    return payload.model_dump(mode="json")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send_notification(request: SendRequest) -> dict:
    _assert_permission(request.actor_role, "notification:send")
    payload = NotificationPayload(
        payload_id=f"NTF-{uuid4().hex[:10].upper()}",
        user_id=request.user_id,
        channel=request.channel,
        alert_type=request.alert_type,
        subject=request.subject,
        body=request.body,
    )
    return _queue(payload)


@app.post("/notify/new-paper")
async def notify_new_paper(request: NewPaperRequest) -> dict:
    _assert_permission(request.actor_role, "notification:send")
    queued = []
    for user_id in request.user_ids:
        subject = f"New paper: {request.title}"
        keyword_text = ", ".join(request.matched_keywords[:5]) if request.matched_keywords else "subscription match"
        payload = NotificationPayload(
            payload_id=f"NTF-{uuid4().hex[:10].upper()}",
            user_id=user_id,
            channel=NotificationChannel.IN_APP,
            alert_type=AlertType.NEW_PAPER,
            subject=subject,
            body=f"Paper {request.paper_id} matched keywords: {keyword_text}",
            paper_id=request.paper_id,
        )
        queued.append(_queue(payload))
    return {"count": len(queued), "items": queued}


@app.post("/notify/citation")
async def notify_citation(request: CitationRequest) -> dict:
    _assert_permission(request.actor_role, "notification:send")
    payload = NotificationPayload(
        payload_id=f"NTF-{uuid4().hex[:10].upper()}",
        user_id=request.user_id,
        channel=NotificationChannel.EMAIL,
        alert_type=AlertType.NEW_CITATION,
        subject=f"Your paper {request.paper_id} was cited",
        body=f"New citation by {request.citation_by}",
        paper_id=request.paper_id,
        citation_by=request.citation_by,
    )
    return _queue(payload)


@app.post("/notify/digest")
async def notify_digest(request: DigestRequest) -> dict:
    _assert_permission(request.actor_role, "notification:send")
    payload = NotificationPayload(
        payload_id=f"NTF-{uuid4().hex[:10].upper()}",
        user_id=request.user_id,
        channel=NotificationChannel.EMAIL,
        alert_type=AlertType.PERSONAL_DIGEST,
        subject="Your ResearchNet digest",
        body=request.digest,
    )
    return _queue(payload)


@app.get("/notify/history")
async def history(user_id: str | None = None, alert_type: AlertType | None = None) -> dict:
    items = []
    for message in messages:
        if user_id and message.user_id != user_id:
            continue
        if alert_type and message.alert_type != alert_type:
            continue
        items.append(message.model_dump(mode="json"))
    return {"items": items, "count": len(items)}
