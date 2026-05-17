# Deployment

## Requirements

- Docker
- Docker Compose
- Python 3.11 for local checks

## Start

```bash
cd d:\Шарага\Кинжа2\Task_13_ResearchNet
docker compose up --build -d
```

## Stop

```bash
docker compose down
```

## Validate

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Ports

- `8500` gateway
- `5178` frontend
- `8501-8507` backend services
- `55435` PostgreSQL
- `57687` Neo4j Bolt
- `59200` Elasticsearch
- `59000` MinIO API
- `55672` RabbitMQ AMQP
