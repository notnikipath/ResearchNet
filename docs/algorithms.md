# Algorithms

## Full-text and semantic search

- Token overlap, citation bonus, and recency bonus for full-text ranking
- Jaccard-style semantic score over title/abstract/keywords/topics
- Query cache with TTL for repeated requests

## Citation graph and key paper detection

- Directed edges from citing paper to referenced paper
- Author metrics: h-index and i10-index from citation count vectors
- Journal impact-factor approximation: citations in last two years / citable items
- Key paper score combines citation volume, recency, and graph centrality proxy

## Recommendation engine

- Content-based similarity: topic overlap + textual similarity + citation prior
- Collaborative boost: user favorites overlap (Jaccard over user sets)
- Expert recommendations by topic and h-index weight

## Intelligent improvements

- Summarization: extractive sentence ranking by keyword density
- Topic clustering: frequency-based grouping by topic labels
- Breakthrough forecasting: slope + growth score transformed to probability

## Performance helpers

- Parallel PDF processing plan: worker and batch sizing heuristic
- Async indexing queue for non-blocking update paths
- Topic shard map for graph partition planning

## Search quality metrics

- Precision@10
- NDCG@10
- Targets checked by service:
  - `NDCG@10 > 0.8`
  - `Precision@10 > 0.7`
