from __future__ import annotations

import math


def precision_at_k(ranked_ids: list[str], relevant_ids: list[str], k: int = 10) -> float:
    if k <= 0:
        return 0.0
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    relevant = set(relevant_ids)
    hits = sum(1 for item in top_k if item in relevant)
    return round(hits / len(top_k), 4)


def _dcg(ids: list[str], relevant: set[str], k: int = 10) -> float:
    score = 0.0
    for idx, item in enumerate(ids[:k], start=1):
        rel = 1.0 if item in relevant else 0.0
        score += rel / math.log2(idx + 1)
    return score


def ndcg_at_k(ranked_ids: list[str], relevant_ids: list[str], k: int = 10) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    dcg = _dcg(ranked_ids, relevant, k=k)
    ideal = _dcg(list(relevant), relevant, k=min(k, len(relevant)))
    if ideal == 0:
        return 0.0
    return round(dcg / ideal, 4)


def h_index(citation_counts: list[int]) -> int:
    if not citation_counts:
        return 0
    ordered = sorted((max(0, int(value)) for value in citation_counts), reverse=True)
    h = 0
    for idx, cites in enumerate(ordered, start=1):
        if cites >= idx:
            h = idx
        else:
            break
    return h


def i10_index(citation_counts: list[int]) -> int:
    return sum(1 for value in citation_counts if value >= 10)


def impact_factor(citations_in_window: int, citable_items: int) -> float:
    if citable_items <= 0:
        return 0.0
    return round(citations_in_window / citable_items, 4)


def key_paper_score(citations: int, recency_years: float, pagerank_like: float) -> float:
    citation_component = math.log1p(max(citations, 0)) * 4.5
    recency_component = max(0.2, 1 / (1 + max(recency_years, 0))) * 3.0
    graph_component = max(0.0, min(1.0, pagerank_like)) * 2.5
    return round(citation_component + recency_component + graph_component, 4)


def indexing_rate_per_hour(processed_count: int, elapsed_minutes: float) -> float:
    if elapsed_minutes <= 0:
        return 0.0
    return round(processed_count * 60 / elapsed_minutes, 2)
