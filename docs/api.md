# API Overview

## Gateway

- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `POST /workflow/add-source`
- `POST /workflow/process-paper`
- `POST /workflow/process-batch`
- `POST /search`
- `POST /search/semantic`
- `GET /dashboard/{paper_id}/{user_id}`

## Ingestion service

- `GET /sources`
- `POST /sources`
- `POST /sources/sync`
- `POST /providers/fetch`
- `POST /papers/ingest`
- `POST /papers/ingest/batch`
- `GET /papers`
- `GET /papers/{paper_id}`
- `GET /stats`

## Search service

- `POST /index/paper`
- `POST /index/bulk`
- `POST /index/queue`
- `GET /index/queue/{queue_id}`
- `POST /search`
- `POST /search/semantic`
- `POST /search/evaluate`
- `GET /search/cache/stats`
- `GET /index/stats`

## Citation service

- `POST /citations/build`
- `POST /citations/edge`
- `GET /citations/graph`
- `GET /citations/graph/shards`
- `GET /metrics/author/{author_id}`
- `GET /metrics/journal/{journal}`
- `GET /works/key`

## Recommendation service

- `POST /recommendations/rebuild`
- `POST /recommendations/update/{paper_id}`
- `POST /recommendations/similar`
- `GET /recommendations/paper/{paper_id}`
- `POST /interactions/favorite`
- `GET /recommendations/experts`
- `GET /clusters/topics`
- `GET /trends/forecast`
- `GET /quality/precision`
- `GET /digests/{user_id}`

## Visualization service

- `POST /visualization/refresh`
- `GET /graphs/coauthors`
- `GET /graphs/coauthors/interactive`
- `GET /graphs/citations`
- `GET /trends/topics`
- `GET /dashboards/overview`

## User service

- `GET /users`
- `POST /users`
- `GET /users/{user_id}`
- `POST /users/{user_id}/orcid/link`
- `POST /users/{user_id}/favorites/{paper_id}`
- `GET /users/{user_id}/favorites`
- `POST /subscriptions`
- `GET /subscriptions/{user_id}`
- `GET /exports/{user_id}?format=bibtex|ris`

## Notification service

- `POST /notify/send`
- `POST /notify/new-paper`
- `POST /notify/citation`
- `POST /notify/digest`
- `GET /notify/history`
