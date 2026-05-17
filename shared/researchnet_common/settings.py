from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "researchnet-service"
    service_port: int = 8500
    environment: str = "dev"

    postgres_dsn: str = "postgresql+psycopg://researchnet:researchnet@postgres:5432/researchnet"
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "researchnet"
    elasticsearch_url: str = "http://elasticsearch:9200"
    minio_url: str = "http://minio:9000"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672//"

    jwt_secret: str = "researchnet-dev-secret"
    encryption_key: str = "researchnet-dev-encryption-key"

    search_target_ms: float = 1000.0
    precision_target: float = 0.7
    ndcg_target: float = 0.8
    papers_capacity_target: int = 10_000_000
    indexing_target_per_hour: int = 1000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
