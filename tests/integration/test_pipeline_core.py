from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

ingestion_module = load_module("ingestion_module", ROOT / "ingestion-service" / "app" / "main.py")
search_module = load_module("search_module", ROOT / "search-service" / "app" / "main.py")
citation_module = load_module("citation_module", ROOT / "citation-service" / "app" / "main.py")
recommendation_module = load_module("recommendation_module", ROOT / "recommendation-service" / "app" / "main.py")
visualization_module = load_module("visualization_module", ROOT / "visualization-service" / "app" / "main.py")
user_module = load_module("user_module", ROOT / "user-service" / "app" / "main.py")
notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")

ingestion_client = TestClient(ingestion_module.app)
search_client = TestClient(search_module.app)
citation_client = TestClient(citation_module.app)
recommendation_client = TestClient(recommendation_module.app)
visualization_client = TestClient(visualization_module.app)
user_client = TestClient(user_module.app)
notification_client = TestClient(notification_module.app)


def test_end_to_end_publication_flow() -> None:
    ingest = ingestion_client.post(
        "/papers/ingest",
        json={
            "metadata": {
                "paper_id": "PPR-INT-001",
                "title": "Cross-lingual Citation Graph Expansion",
                "abstract": "Pipeline for cross-lingual citation graph construction.",
                "keywords": ["citation graph", "cross-lingual retrieval"],
                "authors": [
                    {
                        "author_id": "AUTH-INT-01",
                        "name": "Elena Smirnova",
                        "affiliation": "HSE",
                        "orcid_id": "0000-1111-2222",
                    }
                ],
                "source_type": "preprint",
                "source_name": "arXiv",
                "year": 2026,
                "doi": "10.1000/rn.int.001",
                "language": "en",
                "citations_count": 0,
                "references": [
                    {
                        "ref_id": "REF-INT-1",
                        "title": "Graph Neural Networks for Citation Recommendation",
                        "authors": ["Anna Petrova"],
                        "year": 2024,
                        "doi": "10.1000/rn.2024.001",
                        "paper_id": "PPR-DEMO-001",
                    }
                ],
                "topics": ["citation graph", "knowledge graph"],
                "is_preprint": True,
            },
            "pdf_text": "Intro. REF: Graph Neural Networks for Citation Recommendation.",
            "actor_id": "ADM-001",
            "actor_role": "admin",
        },
    )
    assert ingest.status_code == 200
    paper = ingest.json()["paper"]

    index = search_client.post("/index/paper", json=paper)
    assert index.status_code == 200

    build_graph = citation_client.post("/citations/build", json={"paper": paper})
    assert build_graph.status_code == 200
    assert build_graph.json()["edges_created"] >= 1

    papers = ingestion_client.get("/papers")
    assert papers.status_code == 200

    users = user_client.get("/users")
    assert users.status_code == 200
    favorites = {item["user_id"]: item.get("favorites", []) for item in users.json()["items"]}

    rebuild = recommendation_client.post(
        "/recommendations/rebuild",
        json={
            "papers": papers.json()["items"],
            "user_favorites": favorites,
            "actor_id": "ADM-001",
            "actor_role": "admin",
        },
    )
    assert rebuild.status_code == 200

    recs = recommendation_client.get(f"/recommendations/paper/{paper['paper_id']}")
    assert recs.status_code == 200

    graph = citation_client.get("/citations/graph")
    assert graph.status_code == 200

    viz = visualization_client.post(
        "/visualization/refresh",
        json={
            "papers": papers.json()["items"],
            "citation_edges": graph.json()["edges"],
            "actor_role": "admin",
        },
    )
    assert viz.status_code == 200

    notify = notification_client.post(
        "/notify/new-paper",
        json={
            "user_ids": ["USR-001", "USR-002"],
            "paper_id": paper["paper_id"],
            "title": paper["title"],
            "matched_keywords": paper["keywords"],
            "actor_role": "admin",
        },
    )
    assert notify.status_code == 200
    assert notify.json()["count"] == 2



def test_search_quality_multiuser_and_exports() -> None:
    search_result = search_client.post(
        "/search",
        json={
            "query": "citation recommendation graph",
            "mode": "fulltext",
            "filters": {"citations_min": 0},
            "limit": 10,
        },
    )
    assert search_result.status_code == 200
    ranked_ids = [item["paper_id"] for item in search_result.json()["hits"]]
    assert ranked_ids

    quality = search_client.post(
        "/search/evaluate",
        json={
            "ranked_ids": ranked_ids,
            "relevant_ids": ["PPR-DEMO-001", "PPR-INT-001"],
        },
    )
    assert quality.status_code == 200
    payload = quality.json()
    assert payload["ndcg_at_10"] >= 0
    assert payload["precision_at_10"] >= 0

    favorite = user_client.post(
        "/users/USR-001/favorites/PPR-INT-001",
        json={"actor_id": "USR-001", "actor_role": "researcher"},
    )
    assert favorite.status_code == 200

    export = user_client.get("/exports/USR-001", params={"format": "bibtex"})
    assert export.status_code == 200
    assert export.json()["count"] >= 1

    digest = recommendation_client.get("/digests/USR-001")
    assert digest.status_code == 200

    digest_notice = notification_client.post(
        "/notify/digest",
        json={
            "user_id": "USR-001",
            "digest": digest.json()["digest"],
            "actor_role": "admin",
        },
    )
    assert digest_notice.status_code == 200
