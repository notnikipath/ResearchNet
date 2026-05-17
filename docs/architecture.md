# Architecture

## Context

ResearchNet provides end-to-end publication lifecycle support:

1. Metadata collection from open providers
2. PDF text and reference extraction
3. Search indexing
4. Citation graph update
5. Recommendations refresh
6. Visualization refresh and notifications

## Service map

- `api-gateway`: entry point, auth, workflow orchestration
- `ingestion-service`: source configuration, metadata parsing, batch ingest pipeline
- `search-service`: fulltext + semantic retrieval, filters, cache, NDCG and precision checks
- `citation-service`: citation graph, h-index, i10-index, impact-factor, key works
- `recommendation-service`: content and collaborative ranking, expert recommendation, topic clustering
- `visualization-service`: coauthor network, citation links, topic trend datasets for D3
- `user-service`: profiles, ORCID linking, favorites, subscription and bibliography export
- `notification-service`: new-paper alerts, citation alerts, personalized digests

## Data layer and infrastructure

- PostgreSQL for structured metadata and account data
- Neo4j for citation and coauthor graph storage path
- Elasticsearch for low-latency search and scoring
- MinIO for PDF object storage
- RabbitMQ for async pipeline tasks and queueing

## Core pipeline

`Collect -> Extract -> Index -> CitationGraph -> Recommendations -> Visualization -> Notifications`

Gateway endpoint: `POST /workflow/process-paper`

## Security and compliance

- Roles: `reader`, `researcher`, `admin`
- Permission checks in every service
- Audit logs in ingestion/citation/recommendation/user services

## Scalability notes

- Async index queue endpoint for batched updates
- Search cache for high-QPS repeated queries
- Parallel PDF plan for ingestion batches
- Topic-based citation shard view for graph partition planning
- Stateless FastAPI services behind gateway for horizontal scaling
