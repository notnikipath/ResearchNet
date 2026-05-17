from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from shared.researchnet_common import CitationEdge, PaperDocument, Role, Settings

settings = Settings(service_name="visualization-service", service_port=8505)
app = FastAPI(title="ResearchNet Visualization Service", version="1.0.0")


class RefreshPayload(BaseModel):
    papers: list[PaperDocument] = Field(default_factory=list)
    citation_edges: list[CitationEdge] = Field(default_factory=list)
    actor_role: Role = Role.ADMIN


RefreshPayload.model_rebuild()


papers: dict[str, PaperDocument] = {}
citation_edges: list[CitationEdge] = []


def _coauthor_graph() -> dict:
    node_counter: dict[str, dict] = {}
    edge_weights: Counter[tuple[str, str]] = Counter()

    for paper in papers.values():
        authors = [author.name for author in paper.authors]
        for author in paper.authors:
            node_counter.setdefault(
                author.author_id,
                {
                    "id": author.author_id,
                    "label": author.name,
                    "affiliation": author.affiliation,
                    "papers": 0,
                },
            )
            node_counter[author.author_id]["papers"] += 1

        for left, right in combinations(sorted(authors), 2):
            edge_weights[(left, right)] += 1

    name_to_id = {node["label"]: node["id"] for node in node_counter.values()}
    links = []
    for (left, right), weight in edge_weights.items():
        if left not in name_to_id or right not in name_to_id:
            continue
        links.append({"source": name_to_id[left], "target": name_to_id[right], "weight": weight})

    nodes = list(node_counter.values())
    nodes.sort(key=lambda item: item["papers"], reverse=True)
    return {"nodes": nodes, "links": links}


def _topic_trends() -> list[dict]:
    topic_years: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for paper in papers.values():
        for topic in paper.topics[:3]:
            topic_years[topic.lower()][paper.year] += 1

    rows = []
    for topic, series in topic_years.items():
        ordered = sorted(series.items())
        rows.append(
            {
                "topic": topic,
                "points": [{"year": year, "count": count} for year, count in ordered],
                "latest": ordered[-1][1] if ordered else 0,
            }
        )

    rows.sort(key=lambda item: item["latest"], reverse=True)
    return rows


def _citation_degree() -> dict[str, int]:
    degrees: dict[str, int] = Counter()
    for edge in citation_edges:
        degrees[edge.citing_paper_id] += 1
        degrees[edge.cited_paper_id] += 1
    return dict(degrees)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/visualization/refresh")
async def refresh(payload: RefreshPayload) -> dict:
    for paper in payload.papers:
        papers[paper.paper_id] = paper
    citation_edges.clear()
    citation_edges.extend(payload.citation_edges)
    return {"status": "ok", "papers": len(papers), "edges": len(citation_edges)}


@app.get("/graphs/coauthors")
async def coauthors_graph() -> dict:
    return _coauthor_graph()


@app.get("/graphs/coauthors/interactive")
async def coauthors_interactive() -> dict:
    graph = _coauthor_graph()
    nodes = graph["nodes"]
    for idx, node in enumerate(nodes, start=1):
        node["x"] = (idx % 5) * 120 + 40
        node["y"] = (idx // 5) * 120 + 40
        node["group"] = node.get("affiliation") or "independent"
    return {"nodes": nodes, "links": graph["links"], "layout": "force-ready"}


@app.get("/graphs/citations")
async def citation_graph() -> dict:
    degrees = _citation_degree()
    nodes = []
    for paper in papers.values():
        nodes.append(
            {
                "id": paper.paper_id,
                "label": paper.title,
                "citations": paper.citations_count,
                "degree": degrees.get(paper.paper_id, 0),
                "year": paper.year,
            }
        )
    links = [edge.model_dump(mode="json") for edge in citation_edges]
    return {"nodes": nodes, "links": links}


@app.get("/trends/topics")
async def topic_trends() -> dict:
    rows = _topic_trends()
    return {"items": rows, "count": len(rows)}


@app.get("/dashboards/overview")
async def overview() -> dict:
    source_counts = Counter(paper.source_type.value for paper in papers.values())
    languages = Counter(paper.language.value for paper in papers.values())
    trend_rows = _topic_trends()
    coauthors = _coauthor_graph()

    return {
        "papers_total": len(papers),
        "citation_edges_total": len(citation_edges),
        "source_distribution": dict(source_counts),
        "language_distribution": dict(languages),
        "top_topics": [row["topic"] for row in trend_rows[:5]],
        "coauthor_nodes": len(coauthors["nodes"]),
        "coauthor_links": len(coauthors["links"]),
    }


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
            citations_count=48,
            references=[],
            topics=["graph mining", "recommender systems", "scientometrics"],
            full_text="...",
            summary="...",
        ),
        PaperDocument(
            paper_id="PPR-DEMO-002",
            title="Multilingual Semantic Search for Scientific Archives",
            abstract="Embeddings for Russian and English scientific retrieval.",
            keywords=["semantic search", "multilingual", "embeddings"],
            authors=[
                {"author_id": "AUTH-003", "name": "Irina Volkova", "affiliation": "ITMO"},
                {"author_id": "AUTH-001", "name": "Anna Petrova", "affiliation": "MSU"},
            ],
            source_type="conference",
            source_name="AI Systems Conf",
            year=2025,
            citations_count=19,
            references=[],
            topics=["semantic retrieval", "multilingual nlp"],
            full_text="...",
            summary="...",
        ),
        PaperDocument(
            paper_id="PPR-DEMO-003",
            title="Patent Trend Forecasting with Citation Dynamics",
            abstract="Breakthrough detection in patent families using citation trajectories.",
            keywords=["patents", "forecasting", "citation dynamics"],
            authors=[
                {"author_id": "AUTH-004", "name": "Liu Wei", "affiliation": "Tsinghua"},
                {"author_id": "AUTH-002", "name": "John Smith", "affiliation": "MIT"},
            ],
            source_type="patent",
            source_name="Global Patent Bulletin",
            year=2023,
            citations_count=32,
            references=[],
            topics=["trend forecasting", "patent analytics"],
            full_text="...",
            summary="...",
        ),
    ]

    for paper in seeded:
        papers[paper.paper_id] = paper

    citation_edges.extend(
        [
            CitationEdge(citing_paper_id="PPR-DEMO-001", cited_paper_id="PPR-DEMO-002", year=2024),
            CitationEdge(citing_paper_id="PPR-DEMO-001", cited_paper_id="PPR-DEMO-003", year=2024),
            CitationEdge(citing_paper_id="PPR-DEMO-003", cited_paper_id="PPR-DEMO-001", year=2023),
        ]
    )


_seed()
