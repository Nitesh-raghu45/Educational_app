import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import auth, documents, quizzes, sections
from .config import get_settings
from .db import create_tables, engine
from .errors import AppError
from .ratelimit import get_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def redis_status() -> str:
    client = get_redis()
    if client is None:
        return "disabled"
    try:
        await client.ping()
        return "connected"
    except Exception as exc:
        return f"unreachable ({type(exc).__name__})"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP: create tables on boot. Switch to Alembic migrations before running several replicas.
    await create_tables()
    status = await redis_status()
    settings = get_settings()
    if status == "connected":
        logger.info("Redis connected: rate limiting on, ingestion mode=%s", settings.ingest_mode)
    elif status == "disabled":
        logger.info("Redis disabled (REDIS_URL empty): rate limiting off")
    else:
        logger.warning("Redis %s: check REDIS_URL. Rate limiting is skipped until it is reachable.", status)
    yield
    await engine.dispose()


app = FastAPI(title="Study Assistant API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_body())


for router in (auth.router, sections.router, documents.router, quizzes.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "redis": await redis_status()}
