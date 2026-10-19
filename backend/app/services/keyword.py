"""BM25 keyword search over the chunk text stored in the database.

Complements vector search for exact terms (names, formulas, codes, rare words) that embeddings
can miss. Per-document term statistics are cached in memory and rebuilt when a document is
re-ingested (its `updated_at` changes), so a query only tokenises the question.
"""

import asyncio
import math
import re
import uuid
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Document, DocumentChunk

K1 = 1.5
B = 0.75
MAX_CACHED_DOCUMENTS = 512

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have
    having he her here hers herself him himself his how i if in into is it its itself just me more most my
    myself no nor not now of off on once only or other our ours ourselves out over own same she should so
    some such than that the their theirs them themselves then there these they this those through to too
    under until up very was we were what when where which while who whom why will with would you your
    yours yourself yourselves explain tell describe define give list""".split()
)

try:
    from py_rust_stemmers import SnowballStemmer  # installed with fastembed

    _stem = SnowballStemmer("english").stem_word
except ImportError:  # pragma: no cover
    def _stem(word: str) -> str:
        return word


def tokenize(text: str) -> list[str]:
    tokens = []
    for word in _TOKEN_RE.findall(text.lower()):
        if word in _STOPWORDS or (len(word) == 1 and not word.isdigit()):
            continue
        tokens.append(_stem(word))
    return tokens


@dataclass
class _DocumentIndex:
    version: datetime
    chunk_ids: list[str]
    term_freqs: list[Counter]
    lengths: list[int]
    doc_freq: Counter


_cache: "OrderedDict[uuid.UUID, _DocumentIndex]" = OrderedDict()


def _build_index(version: datetime, rows: list[tuple[str, str]]) -> _DocumentIndex:
    chunk_ids, term_freqs, lengths, doc_freq = [], [], [], Counter()
    for chunk_id, text in rows:
        tokens = tokenize(text)
        counts = Counter(tokens)
        chunk_ids.append(chunk_id)
        term_freqs.append(counts)
        lengths.append(len(tokens))
        doc_freq.update(counts.keys())
    return _DocumentIndex(version, chunk_ids, term_freqs, lengths, doc_freq)


async def _indexes(
    session: AsyncSession, user_id: uuid.UUID, document_ids: list[uuid.UUID]
) -> list[_DocumentIndex]:
    versions = dict(
        (
            await session.execute(
                select(Document.id, Document.updated_at).where(
                    Document.id.in_(document_ids), Document.user_id == user_id
                )
            )
        ).all()
    )
    stale = [doc_id for doc_id, version in versions.items() if (cached := _cache.get(doc_id)) is None or cached.version != version]
    if stale:
        rows = await session.execute(
            select(DocumentChunk.document_id, DocumentChunk.id, DocumentChunk.text)
            .where(DocumentChunk.document_id.in_(stale))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        by_document: dict[uuid.UUID, list[tuple[str, str]]] = {doc_id: [] for doc_id in stale}
        for document_id, chunk_id, text in rows:
            by_document[document_id].append((chunk_id, text))
        for doc_id, chunk_rows in by_document.items():
            _cache[doc_id] = await asyncio.to_thread(_build_index, versions[doc_id], chunk_rows)
    for doc_id in versions:
        _cache.move_to_end(doc_id)
    while len(_cache) > MAX_CACHED_DOCUMENTS:
        _cache.popitem(last=False)
    return [_cache[doc_id] for doc_id in versions]


async def keyword_search(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    query: str,
    top_k: int,
) -> list[tuple[str, float]]:
    """Returns (chunk_id, bm25_score), best first, across the given documents."""
    terms = set(tokenize(query))
    if not terms or not document_ids:
        return []
    indexes = await _indexes(session, user_id, document_ids)
    total_chunks = sum(len(ix.chunk_ids) for ix in indexes)
    if total_chunks == 0:
        return []
    avg_length = sum(sum(ix.lengths) for ix in indexes) / total_chunks or 1.0
    idf = {}
    for term in terms:
        df = sum(ix.doc_freq.get(term, 0) for ix in indexes)
        idf[term] = math.log(1 + (total_chunks - df + 0.5) / (df + 0.5))
    # One shared word is too weak a signal for multi-word questions (it's usually incidental).
    min_matched = 1 if len(terms) == 1 else 2

    scored = []
    for ix in indexes:
        for chunk_id, counts, length in zip(ix.chunk_ids, ix.term_freqs, ix.lengths):
            matched = [t for t in terms if t in counts]
            if len(matched) < min_matched:
                continue
            norm = K1 * (1 - B + B * length / avg_length)
            score = sum(idf[t] * counts[t] * (K1 + 1) / (counts[t] + norm) for t in matched)
            scored.append((chunk_id, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]
