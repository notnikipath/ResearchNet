from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    JOURNAL = "journal"
    CONFERENCE = "conference"
    PREPRINT = "preprint"
    PATENT = "patent"
    BOOK_CHAPTER = "book_chapter"


class ProviderType(str, Enum):
    CROSSREF = "crossref"
    PUBMED = "pubmed"
    IEEE = "ieee"
    ARXIV = "arxiv"
    BIORXIV = "biorxiv"
    MANUAL = "manual"


class Role(str, Enum):
    READER = "reader"
    RESEARCHER = "researcher"
    ADMIN = "admin"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class AlertType(str, Enum):
    NEW_PAPER = "new_paper"
    NEW_CITATION = "new_citation"
    PERSONAL_DIGEST = "personal_digest"


class SearchMode(str, Enum):
    FULLTEXT = "fulltext"
    SEMANTIC = "semantic"


class ScheduleFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class PaperLanguage(str, Enum):
    RU = "ru"
    EN = "en"
    MULTI = "multi"


class PaperStatus(str, Enum):
    COLLECTED = "collected"
    INDEXED = "indexed"
    CITATION_ANALYZED = "citation_analyzed"
    RECOMMENDATIONS_UPDATED = "recommendations_updated"


class Author(BaseModel):
    author_id: str
    name: str
    affiliation: str | None = None
    orcid_id: str | None = None


class ReferenceEntry(BaseModel):
    ref_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    paper_id: str | None = None


class SourceConfig(BaseModel):
    source_id: str
    name: str
    source_type: SourceType
    provider: ProviderType = ProviderType.MANUAL
    api_url: str | None = None
    is_active: bool = True
    update_frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    topics: list[str] = Field(default_factory=list)
    last_sync_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceSyncRequest(BaseModel):
    source_id: str
    force: bool = False
    actor_id: str
    actor_role: Role


class PaperMetadata(BaseModel):
    paper_id: str
    title: str
    abstract: str
    keywords: list[str] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    source_type: SourceType
    source_name: str
    year: int = Field(ge=1900, le=2100)
    published_at: datetime | None = None
    doi: str | None = None
    language: PaperLanguage = PaperLanguage.EN
    pdf_url: str | None = None
    citations_count: int = Field(default=0, ge=0)
    references: list[ReferenceEntry] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    is_preprint: bool = False


class PaperIngestRequest(BaseModel):
    metadata: PaperMetadata
    pdf_text: str | None = None
    actor_id: str
    actor_role: Role


class PaperDocument(BaseModel):
    paper_id: str
    title: str
    abstract: str
    keywords: list[str]
    authors: list[Author]
    source_type: SourceType
    source_name: str
    year: int
    published_at: datetime | None = None
    doi: str | None = None
    language: PaperLanguage = PaperLanguage.EN
    pdf_url: str | None = None
    citations_count: int = Field(default=0, ge=0)
    references: list[ReferenceEntry] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    status: PaperStatus = PaperStatus.COLLECTED
    full_text: str = ""
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaperBatchRequest(BaseModel):
    items: list[PaperIngestRequest] = Field(default_factory=list)


class SearchFilters(BaseModel):
    author_id: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    journal: str | None = None
    citations_min: int | None = None
    source_types: list[SourceType] = Field(default_factory=list)
    language: PaperLanguage | None = None


class SearchRequest(BaseModel):
    query: str
    mode: SearchMode = SearchMode.FULLTEXT
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=10, ge=1, le=100)


class SearchHit(BaseModel):
    paper_id: str
    score: float
    title: str
    snippet: str
    authors: list[str] = Field(default_factory=list)
    year: int
    source_name: str


class SearchResponse(BaseModel):
    total: int
    latency_ms: float
    hits: list[SearchHit] = Field(default_factory=list)
    cache_hit: bool = False


class CitationEdge(BaseModel):
    citing_paper_id: str
    cited_paper_id: str
    weight: int = Field(default=1, ge=1)
    year: int | None = None


class CitationBuildRequest(BaseModel):
    paper: PaperDocument


class CitationGraphSnapshot(BaseModel):
    nodes: list[str] = Field(default_factory=list)
    edges: list[CitationEdge] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuthorCitationMetrics(BaseModel):
    author_id: str
    papers: int
    citations: int
    h_index: int
    i10_index: int


class JournalMetrics(BaseModel):
    journal: str
    year: int
    impact_factor: float
    citations_in_window: int
    citable_items: int


class KeyPaper(BaseModel):
    paper_id: str
    title: str
    score: float
    reason: str


class RecommendationRequest(BaseModel):
    paper_id: str
    user_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RecommendationItem(BaseModel):
    paper_id: str
    score: float
    reason: str
    shared_topics: list[str] = Field(default_factory=list)


class ExpertRecommendation(BaseModel):
    expert_id: str
    name: str
    topic: str
    score: float
    h_index: int
    top_papers: list[str] = Field(default_factory=list)


class TopicCluster(BaseModel):
    cluster_id: str
    label: str
    paper_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    size: int = 0


class TrendForecast(BaseModel):
    topic: str
    slope: float
    growth_score: float
    breakthrough_probability: float


class RecommendationUpdateRequest(BaseModel):
    papers: list[PaperDocument] = Field(default_factory=list)
    users: list[UserProfile] = Field(default_factory=list)


class UserProfile(BaseModel):
    user_id: str
    name: str
    email: str
    role: Role = Role.READER
    affiliation: str | None = None
    research_interests: list[str] = Field(default_factory=list)
    orcid_id: str | None = None
    favorites: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Subscription(BaseModel):
    subscription_id: str
    user_id: str
    keywords: list[str] = Field(default_factory=list)
    author_ids: list[str] = Field(default_factory=list)
    journal_filters: list[str] = Field(default_factory=list)
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SubscriptionCreateRequest(BaseModel):
    user_id: str
    keywords: list[str] = Field(default_factory=list)
    author_ids: list[str] = Field(default_factory=list)
    journal_filters: list[str] = Field(default_factory=list)
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY


class FavoriteEvent(BaseModel):
    user_id: str
    paper_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NotificationPayload(BaseModel):
    payload_id: str
    user_id: str
    channel: NotificationChannel
    alert_type: AlertType
    subject: str
    body: str
    paper_id: str | None = None
    citation_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowResult(BaseModel):
    paper: dict[str, Any]
    index_result: dict[str, Any]
    citation_result: dict[str, Any]
    recommendation_result: dict[str, Any]
    visualization_result: dict[str, Any]
    notification_result: dict[str, Any]
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvalSample(BaseModel):
    ranked_ids: list[str]
    relevant_ids: list[str]


class SearchQualityReport(BaseModel):
    ndcg_at_10: float
    precision_at_10: float
    meets_ndcg_target: bool
    meets_precision_target: bool


RecommendationUpdateRequest.model_rebuild()
