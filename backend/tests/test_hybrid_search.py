import uuid

from app.db import SessionLocal
from app.services.keyword import keyword_search, tokenize
from app.services.retrieval import reciprocal_rank_fusion, retrieve

from .conftest import register
from .test_chat import new_section, upload_ready_doc

NOTES = (
    "Enzymes are proteins that speed up chemical reactions in cells.\n\n"
    "The XR-17 protocol requires samples to be stored at minus 80 degrees Celsius.\n\n"
    "Mitochondria produce ATP through cellular respiration."
)


def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("What are the Enzymes producing?") == ["enzym", "produc"]
    assert "17" in tokenize("XR-17 protocol")


def test_rrf_rewards_items_found_by_both_searches():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "d"]], k=60)
    assert max(fused, key=fused.get) == "c"
    assert set(fused) == {"a", "b", "c", "d"}


async def _setup(client, text=NOTES):
    headers = await register(client)
    section_id = await new_section(client, headers)
    doc_id = await upload_ready_doc(client, headers, section_id, text=text, name="lab-notes.txt")
    user_id = uuid.UUID((await client.get("/api/v1/auth/me", headers=headers)).json()["id"])
    return user_id, uuid.UUID(doc_id)


async def test_keyword_search_finds_exact_terms(client):
    user_id, doc_id = await _setup(client)
    async with SessionLocal() as session:
        hits = await keyword_search(
            session, user_id=user_id, document_ids=[doc_id], query="XR-17 protocol storage", top_k=5
        )
    assert hits and hits[0][1] > 0


async def test_keyword_search_ignores_single_incidental_word(client):
    user_id, doc_id = await _setup(client)
    async with SessionLocal() as session:
        hits = await keyword_search(
            session, user_id=user_id, document_ids=[doc_id], query="Who won the football world cup in cells?", top_k=5
        )
    assert hits == []


async def test_hybrid_returns_keyword_match_when_vector_search_misses(client):
    user_id, doc_id = await _setup(client)
    async with SessionLocal() as session:
        # A min_score of 0.99 makes vector search return nothing, so only keyword search can find it.
        evidence = await retrieve(
            session, user_id=user_id, document_ids=[doc_id], query="XR-17 protocol temperature", top_k=8, min_score=0.99
        )
    assert evidence and evidence[0].matched_by == "keyword"
    assert "XR-17" in evidence[0].text


async def test_hybrid_marks_chunks_found_by_both(client):
    user_id, doc_id = await _setup(client)
    async with SessionLocal() as session:
        evidence = await retrieve(
            session, user_id=user_id, document_ids=[doc_id], query="XR-17 protocol samples stored", top_k=8, min_score=0.1
        )
    assert evidence[0].matched_by == "both"
    assert evidence[0].citation(1)["matched_by"] == "both"
