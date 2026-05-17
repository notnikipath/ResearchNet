# Project Report

## Goal

Build a platform for cataloging scientific publications, citation analytics, recommendation generation, and scientific network visualization.

## Mandatory criteria coverage

1. Full publication processing cycle:
   - metadata ingestion
   - indexing
   - citation graph update
   - recommendation refresh
   - visualization refresh
   - subscriber notifications
2. Search quality:
   - `search-service` exposes `NDCG@10` and `Precision@10` evaluation endpoint
3. Multiuser mode:
   - profiles, favorites, subscriptions, and role-based authorization
4. Scalability path to 10M papers:
   - async indexing queue
   - cache layer
   - graph shard strategy
   - stateless service decomposition

## Performance targets alignment

- Search latency target: `< 1 sec` (service target configured at 1000 ms)
- Recommendation quality target: `precision@10 > 70%`
- Indexing throughput target: `1000 papers/hour`
- Dataset capacity target: `10,000,000 papers`

## Optional improvements delivered

- Summarization
- Topic clustering
- Trend breakthrough forecasting
- ORCID integration hooks
- BibTeX and RIS export
- Search caching
- Parallel PDF processing planning
- Async index updates
- Interactive coauthor graph
- Personalized digest notifications

## Testing

- Unit tests for ranking metrics, citation metrics, summarization, forecasting, export, and security
- Integration tests for end-to-end publication flow and multiuser/export paths
- Load-test stubs for gateway health and dashboard

## Conclusion

ResearchNet delivers the required mandatory functionality and includes advanced intelligent features that improve discovery quality and platform scalability.
