import ssl
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args() -> dict:
    settings = get_settings()
    if not (settings.database_ssl and settings.database_url.startswith("mysql")):
        return {}
    # Env vars often store PEM newlines as a literal backslash-n; restore real newlines.
    ca = settings.database_ssl_ca.replace("\\n", "\n").strip()
    return {"ssl": ssl.create_default_context(cadata=ca or None)}


engine = create_async_engine(
    get_settings().database_url, pool_pre_ping=True, pool_recycle=1800, connect_args=_connect_args()
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def create_tables() -> None:
    from . import models  # noqa: F401  (registers tables on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
