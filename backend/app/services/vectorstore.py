import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import Settings


@dataclass
class Match:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _is_ready(description: Any) -> bool:
    status = getattr(description, "status", None) or {}
    if isinstance(status, dict):
        return bool(status.get("ready"))
    return bool(getattr(status, "ready", False))


class PineconeStore:
    """Thin synchronous wrapper around a Pinecone serverless index (call via asyncio.to_thread)."""

    UPSERT_BATCH = 100
    DELETE_BATCH = 1000

    def __init__(self, settings: Settings):
        self._settings = settings
        self._index = None
        self._lock = threading.Lock()

    def _get_index(self):
        with self._lock:
            if self._index is not None:
                return self._index
            s = self._settings
            if not s.pinecone_api_key:
                raise RuntimeError("PINECONE_API_KEY is not set")
            from pinecone import Pinecone, ServerlessSpec

            pc = Pinecone(api_key=s.pinecone_api_key)
            if s.pinecone_index not in pc.list_indexes().names():
                pc.create_index(
                    name=s.pinecone_index,
                    dimension=s.embedding_dim,
                    metric="cosine",
                    spec=ServerlessSpec(cloud=s.pinecone_cloud, region=s.pinecone_region),
                )
                deadline = time.monotonic() + 120
                while not _is_ready(pc.describe_index(s.pinecone_index)):
                    if time.monotonic() > deadline:
                        raise RuntimeError("Pinecone index was not ready after 120s")
                    time.sleep(2)
            self._index = pc.Index(s.pinecone_index)
            return self._index

    def upsert(self, namespace: str, items: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        index = self._get_index()
        for start in range(0, len(items), self.UPSERT_BATCH):
            batch = items[start : start + self.UPSERT_BATCH]
            index.upsert(
                vectors=[{"id": i, "values": v, "metadata": m} for i, v, m in batch],
                namespace=namespace,
            )

    def query(self, namespace: str, vector: list[float], top_k: int, document_ids: list[str]) -> list[Match]:
        if not document_ids:
            return []
        result = self._get_index().query(
            namespace=namespace,
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter={"document_id": {"$in": document_ids}},
        )
        return [Match(m.id, float(m.score), dict(m.metadata or {})) for m in result.matches]

    def delete(self, namespace: str, ids: list[str]) -> None:
        index = self._get_index()
        for start in range(0, len(ids), self.DELETE_BATCH):
            index.delete(ids=ids[start : start + self.DELETE_BATCH], namespace=namespace)
