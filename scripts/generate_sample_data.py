from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

SOURCE_TYPES = ["journal", "conference", "preprint", "patent", "book_chapter"]
LANGUAGES = ["en", "ru", "multi"]
TOPICS = [
    "graph mining",
    "semantic retrieval",
    "scientometrics",
    "bioinformatics",
    "nlp",
    "computer vision",
    "patent analytics",
    "trend forecasting",
    "knowledge graph",
]
SOURCES = [
    "Journal of Scholarly Data",
    "AI Systems Conf",
    "arXiv",
    "Global Patent Bulletin",
    "Springer Handbook Chapters",
]


def make_record(index: int) -> dict:
    year = random.randint(2017, 2026)
    source_type = random.choice(SOURCE_TYPES)
    topic_a, topic_b = random.sample(TOPICS, 2)
    title = f"ResearchNet sample paper {index} on {topic_a}"

    return {
        "paper_id": f"PPR-{index:07d}",
        "title": title,
        "abstract": f"This paper explores {topic_a} and {topic_b} for large-scale publication analytics.",
        "keywords": [topic_a, topic_b, "researchnet"],
        "authors": [
            {
                "author_id": f"AUTH-{random.randint(1, 6000):04d}",
                "name": f"Author {random.randint(1, 3000)}",
                "affiliation": random.choice(["MSU", "ITMO", "MIPT", "MIT", "ETH Zurich"]),
                "orcid_id": f"0000-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
            }
        ],
        "source_type": source_type,
        "source_name": random.choice(SOURCES),
        "year": year,
        "published_at": (datetime.now(UTC) - timedelta(days=random.randint(1, 4000))).isoformat(),
        "doi": f"10.1000/rn.{year}.{index}",
        "language": random.choice(LANGUAGES),
        "pdf_url": f"https://cdn.researchnet.local/papers/PPR-{index:07d}.pdf",
        "citations_count": random.randint(0, 350),
        "references": [],
        "topics": [topic_a, topic_b],
        "is_preprint": source_type == "preprint",
    }


if __name__ == "__main__":
    random.seed(42)
    payload = [make_record(index) for index in range(1, 20001)]
    output = Path(__file__).resolve().parents[1] / "data" / "samples" / "research_papers.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} records to {output}")
