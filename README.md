# ResearchNet

ResearchNet is a microservice platform for scientific publication discovery, citation analytics, knowledge graph exploration, and personalized recommendations.

## Modules

- `api-gateway` - authentication, orchestration, unified workflow and dashboard
- `ingestion-service` - metadata parsing, source management, PDF text and references extraction
- `search-service` - full-text and semantic search, filters, quality evaluation
- `citation-service` - citation graph build, h-index, impact-factor, key paper detection
- `recommendation-service` - content-based + collaborative recommendations, experts, trends
- `visualization-service` - coauthor graph, citation graph, topic trends, dashboard aggregates
- `user-service` - researcher profiles, favorites, subscriptions, ORCID and bibliography export
- `notification-service` - alerts for new papers, new citations, personalized digests
- `frontend` - React + D3 dashboard

## Supported publication sources

- Journals
- Conferences
- Preprints (`arXiv`, `bioRxiv` via provider mode)
- Patents
- Books and book chapters

## Optional improvements implemented

1. Automatic summarization of papers
2. Topic clustering
3. Trend breakthrough forecasting
4. ORCID profile linking
5. BibTeX and RIS export
6. Search result caching
7. Parallel PDF processing plan
8. Asynchronous index update queue
9. Interactive coauthor graph (D3)
10. Personalized digest notifications

## Tech stack

- Backend: Python FastAPI
- Data: PostgreSQL, Neo4j, Elasticsearch, MinIO
- Queue: RabbitMQ (Celery-compatible)
- Analytics: Pandas, NetworkX-ready utilities
- Frontend: React + D3.js

## Local run

```bash
cd 'your/project/folder'
docker compose up --build -d
```

## Useful URLs

- Frontend: `http://localhost:5178`
- Gateway health: `http://localhost:8500/health`
- Services health: `http://localhost:8500/services/health`
- Swagger: `http://localhost:8500/docs`

## Validation

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Demo workflow

```bash
python scripts/demo_pipeline.py
```

## Sample data

Generate synthetic publication metadata:

```bash
python scripts/generate_sample_data.py
```

Result file: `data/samples/research_papers.json`
