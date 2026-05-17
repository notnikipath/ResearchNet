from __future__ import annotations

import json
import urllib.request

BASE = "http://localhost:8500"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    payload = {
        "metadata": {
            "paper_id": "PPR-DEMO-900",
            "title": "Adaptive Knowledge Graph Expansion for Scientific Discovery",
            "abstract": "A multilingual framework for automatic expansion of citation knowledge graphs.",
            "keywords": ["knowledge graph", "citation", "semantic search"],
            "authors": [
                {
                    "author_id": "AUTH-900",
                    "name": "Vera Antonova",
                    "affiliation": "HSE University",
                    "orcid_id": "0000-9000-0001",
                }
            ],
            "source_type": "preprint",
            "source_name": "arXiv",
            "year": 2026,
            "doi": "10.1000/rn.2026.900",
            "language": "en",
            "citations_count": 0,
            "references": [
                {
                    "ref_id": "REF-1",
                    "title": "Graph Neural Networks for Citation Recommendation",
                    "authors": ["Anna Petrova"],
                    "year": 2024,
                    "doi": "10.1000/rn.2024.001",
                    "paper_id": "PPR-DEMO-001",
                }
            ],
            "topics": ["knowledge graph", "scientometrics", "retrieval"],
            "is_preprint": True,
        },
        "pdf_text": "Introduction and experiments. REF: Graph Neural Networks for Citation Recommendation.",
        "actor_id": "ADM-001",
        "actor_role": "admin",
        "subscriber_user_ids": ["USR-001", "USR-002"],
    }

    result = request("POST", "/workflow/process-paper", payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
