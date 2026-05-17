from shared.researchnet_common import (
    build_personal_digest,
    cluster_topics,
    export_bibtex,
    export_ris,
    forecast_breakthrough,
    jaccard_similarity,
    summarize_text,
)


def test_summary_and_similarity() -> None:
    summary = summarize_text(
        "Scientific search",
        "We evaluate scientific retrieval.",
        "Scientific retrieval is evaluated. We compare sparse and dense indexing strategies.",
    )
    assert summary
    assert jaccard_similarity("graph citation", "graph citation recommendation") > 0



def test_cluster_and_forecast() -> None:
    clusters = cluster_topics(
        [
            {"paper_id": "p1", "topics": ["graph", "retrieval"]},
            {"paper_id": "p2", "topics": ["graph", "nlp"]},
            {"paper_id": "p3", "topics": ["retrieval"]},
        ]
    )
    assert clusters

    forecast = forecast_breakthrough({2022: 2, 2023: 3, 2024: 6, 2025: 8})
    assert forecast["breakthrough_probability"] >= 0



def test_export_and_digest() -> None:
    paper = {
        "paper_id": "P1",
        "title": "Graph Search",
        "source_name": "Journal",
        "year": 2025,
        "doi": "10.1000/xyz",
        "authors": [{"name": "Ada Lovelace"}],
    }
    bib = export_bibtex(paper)
    ris = export_ris(paper)
    digest = build_personal_digest("Alice", ["graph", "nlp"], [paper])

    assert "@article" in bib
    assert "TY  - JOUR" in ris
    assert "Alice" in digest
