from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "using",
    "analysis",
    "study",
    "research",
    "method",
    "results",
    "data",
    "в",
    "и",
    "на",
    "по",
    "с",
    "для",
    "что",
    "как",
    "это",
    "данные",
    "метод",
    "результаты",
    "исследование",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def tokenize(value: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9_\-]{3,}", normalize_text(value))
    return [token for token in tokens if token not in STOPWORDS]


def extract_keywords(title: str, abstract: str, top_k: int = 10) -> list[str]:
    tokens = tokenize(f"{title} {abstract}")
    freq = Counter(tokens)
    return [word for word, _ in freq.most_common(top_k)]


def summarize_text(title: str, abstract: str, full_text: str = "", max_sentences: int = 3) -> str:
    if not full_text.strip():
        full_text = abstract
    sentences = re.split(r"(?<=[.!?])\s+", full_text.strip())
    if not sentences:
        return abstract[:320]
    ranked: list[tuple[float, str]] = []
    keywords = set(extract_keywords(title, abstract, top_k=12))
    for sentence in sentences:
        sentence_tokens = tokenize(sentence)
        overlap = sum(1 for token in sentence_tokens if token in keywords)
        density = overlap / max(len(sentence_tokens), 1)
        ranked.append((density, sentence.strip()))
    ranked.sort(reverse=True, key=lambda item: item[0])
    summary = ". ".join(sentence for _, sentence in ranked[:max_sentences]).strip()
    return summary[:800]


def jaccard_similarity(left_text: str, right_text: str) -> float:
    left_tokens = set(tokenize(left_text))
    right_tokens = set(tokenize(right_text))
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return round(intersection / union, 4)


def semantic_score(query: str, text: str) -> float:
    return jaccard_similarity(query, text)


def collaborative_score(target_paper_id: str, user_favorites: dict[str, list[str]], candidate_paper_id: str) -> float:
    users_for_target = {user_id for user_id, favorites in user_favorites.items() if target_paper_id in favorites}
    if not users_for_target:
        return 0.0
    users_for_candidate = {user_id for user_id, favorites in user_favorites.items() if candidate_paper_id in favorites}
    intersection = len(users_for_target & users_for_candidate)
    union = len(users_for_target | users_for_candidate)
    if union == 0:
        return 0.0
    return round(intersection / union, 4)


def cluster_topics(papers: list[dict], min_cluster_size: int = 2) -> list[dict]:
    topic_map: dict[str, list[str]] = defaultdict(list)
    for paper in papers:
        paper_id = str(paper.get("paper_id"))
        topics = paper.get("topics", []) or paper.get("keywords", [])
        for topic in topics:
            topic_map[str(topic).lower()].append(paper_id)

    clusters = []
    for topic, paper_ids in topic_map.items():
        if len(paper_ids) < min_cluster_size:
            continue
        clusters.append(
            {
                "cluster_id": f"cluster-{abs(hash(topic)) % 10000}",
                "label": topic,
                "paper_ids": sorted(set(paper_ids)),
                "keywords": [topic],
                "size": len(set(paper_ids)),
            }
        )
    clusters.sort(key=lambda item: item["size"], reverse=True)
    return clusters


def forecast_breakthrough(topic_counts_by_year: dict[int, int]) -> dict[str, float]:
    if not topic_counts_by_year:
        return {"slope": 0.0, "growth_score": 0.0, "breakthrough_probability": 0.0}

    points = sorted(topic_counts_by_year.items())
    xs = [float(year) for year, _ in points]
    ys = [float(count) for _, count in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = numerator / denominator if denominator else 0.0

    last = ys[-1]
    first = ys[0]
    growth_score = (last - first) / max(first, 1.0)
    logistic = 1.0 / (1.0 + math.exp(-((slope * 1.3) + growth_score)))
    breakthrough_probability = round(max(0.0, min(1.0, logistic)), 4)

    return {
        "slope": round(slope, 4),
        "growth_score": round(growth_score, 4),
        "breakthrough_probability": breakthrough_probability,
    }


def parallel_pdf_plan(batch_size: int, avg_pages: int, workers_limit: int = 24) -> dict[str, int]:
    workers = min(workers_limit, max(2, batch_size // 8 + avg_pages // 40))
    per_worker = max(1, math.ceil(batch_size / max(workers, 1)))
    return {"workers": workers, "papers_per_worker": per_worker, "batch_size": batch_size}


def shard_topics(papers: list[dict], shards: int = 4) -> dict[str, list[str]]:
    if shards <= 0:
        shards = 1
    mapping: dict[str, list[str]] = {f"shard-{idx + 1}": [] for idx in range(shards)}
    for paper in papers:
        topics = paper.get("topics", [])
        topic_key = "|".join(sorted(str(topic).lower() for topic in topics))
        shard_idx = abs(hash(topic_key or paper.get("paper_id", ""))) % shards
        mapping[f"shard-{shard_idx + 1}"].append(str(paper.get("paper_id")))
    return mapping


def export_bibtex(paper: dict) -> str:
    paper_id = paper.get("paper_id", "unknown")
    first_author = "unknown"
    if paper.get("authors"):
        first_author = paper["authors"][0].get("name", "unknown").split(" ")[-1].lower()
    key = f"{first_author}{paper.get('year', datetime.now(UTC).year)}"
    authors = " and ".join(author.get("name", "") for author in paper.get("authors", []))
    return (
        f"@article{{{key},\n"
        f"  title={{{paper.get('title', '')}}},\n"
        f"  author={{{authors}}},\n"
        f"  journal={{{paper.get('source_name', '')}}},\n"
        f"  year={{{paper.get('year', '')}}},\n"
        f"  doi={{{paper.get('doi', '')}}},\n"
        f"  note={{{paper_id}}}\n"
        "}"
    )


def export_ris(paper: dict) -> str:
    lines = [
        "TY  - JOUR",
        f"TI  - {paper.get('title', '')}",
        f"JO  - {paper.get('source_name', '')}",
        f"PY  - {paper.get('year', '')}",
        f"DO  - {paper.get('doi', '')}",
    ]
    for author in paper.get("authors", []):
        lines.append(f"AU  - {author.get('name', '')}")
    lines.append("ER  -")
    return "\n".join(lines)


def build_personal_digest(user_name: str, topics: list[str], papers: list[dict]) -> str:
    focus = ", ".join(topics[:3]) if topics else "your subscriptions"
    highlights = [paper.get("title", "Untitled") for paper in papers[:3]]
    if highlights:
        bullet = "; ".join(highlights)
    else:
        bullet = "No fresh matches today"
    return f"Hello {user_name}. Focus: {focus}. Highlights: {bullet}."
