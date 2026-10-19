"""arq worker for document ingestion. Run with: arq app.worker.WorkerSettings"""

import logging
import uuid

from .db import create_tables
from .services import providers
from .services.ingestion import ingest_document
from .services.jobs import arq_redis_settings

logging.basicConfig(level=logging.INFO)


async def ingest_document_job(ctx: dict, document_id: str) -> None:
    await ingest_document(uuid.UUID(document_id))


async def startup(ctx: dict) -> None:
    await create_tables()
    # Load the embedding model once up front instead of on the first job.
    providers.embedder().embed_query("warm up")


class WorkerSettings:
    functions = [ingest_document_job]
    on_startup = startup
    redis_settings = arq_redis_settings()
    max_jobs = 2
    job_timeout = 900
