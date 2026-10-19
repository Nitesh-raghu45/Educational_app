from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads ../.env (repo root, used by docker-compose) and ./.env when run from backend/.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "mysql+aiomysql://edu:edu@localhost:3306/edu?charset=utf8mb4"
    redis_url: str = "redis://localhost:6379/0"
    # Cloud Redis over TLS (e.g. Upstash) can take 1-3 s to connect from far away.
    redis_connect_timeout: float = 10.0

    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    storage_dir: str = "./data/uploads"
    max_upload_mb: int = 25
    # "queue" sends ingestion to the arq worker via Redis; "inline" runs it inside the API process.
    ingest_mode: str = "queue"

    max_questions_per_section: int = 30
    rate_limit_per_minute: int = 20

    groq_api_key: str = ""
    # llama-3.3-70b-versatile / llama-3.1-8b-instant were retired on Groq's free/dev tiers (16 Aug 2026).
    # gpt-oss models reason before answering; reasoning_effort trades latency for answer quality.
    groq_answer_model: str = "openai/gpt-oss-120b"
    groq_fast_model: str = "openai/gpt-oss-20b"
    groq_answer_reasoning_effort: str = "medium"
    groq_fast_reasoning_effort: str = "low"

    pinecone_api_key: str = ""
    pinecone_index: str = "education-app"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    # Where the ONNX model is downloaded to (baked into the Docker image at /models).
    embedding_cache_dir: str = "./data/models"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 8
    retrieval_min_score: float = 0.25
    # Hybrid search: BM25 keyword search alongside vector search, merged with reciprocal rank fusion.
    hybrid_search: bool = True
    retrieval_candidates: int = 20
    rrf_k: int = 60
    history_window: int = 8
    summary_min_new_messages: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
