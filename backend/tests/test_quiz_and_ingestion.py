import uuid

from app.services.ingestion import split_text

from .conftest import register
from .test_chat import new_section, upload_ready_doc


def test_split_text_overlaps_and_respects_size():
    text = " ".join(f"word{i}." for i in range(600))
    chunks = split_text(text, size=500, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # Consecutive chunks share some text.
    assert chunks[0][-40:].split()[-1] in chunks[1]


def test_split_text_empty():
    assert split_text("   \n\n  ", 500, 100) == []


async def test_unsupported_upload_rejected(client):
    headers = await register(client)
    response = await client.post(
        "/api/v1/documents", files={"file": ("virus.exe", b"MZ", "application/octet-stream")}, headers=headers
    )
    assert response.status_code == 415


async def test_quiz_generation_and_scoring(client):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)

    response = await client.post(f"/api/v1/sections/{section_id}/quizzes", json={"num_questions": 3}, headers=headers)
    assert response.status_code == 201, response.text
    quiz = response.json()
    # The invalid question (unknown source) was dropped; answers are not exposed.
    assert len(quiz["questions"]) == 1
    assert "answer_index" not in quiz["questions"][0]

    attempt = await client.post(f"/api/v1/quizzes/{quiz['id']}/attempts", json={"answers": [0]}, headers=headers)
    assert attempt.status_code == 201
    body = attempt.json()
    assert (body["score"], body["total"]) == (1, 1)
    assert body["results"][0]["citation"]["filename"] == "biology.txt"


async def test_detached_document_is_not_searched(client):
    headers = await register(client)
    section_id = await new_section(client, headers)
    doc_id = await upload_ready_doc(client, headers, section_id)
    await client.delete(f"/api/v1/sections/{section_id}/documents/{doc_id}", headers=headers)
    response = await client.post(
        f"/api/v1/sections/{section_id}/messages", json={"content": "What is photosynthesis?"}, headers=headers
    )
    assert response.json()["error"]["code"] == "NO_READY_DOCUMENTS"


def test_citations_accept_gpt_oss_bracket_styles():
    from app.services.rag import extract_citations
    from app.services.retrieval import Evidence

    evidence = [Evidence(f"c{i}", uuid.uuid4(), f"doc{i}.pdf", i, "text", 0.9) for i in (1, 2, 3)]
    found = extract_citations("A [1]. B 【2】. C 【3†source】. D [9].", evidence)
    assert [c["index"] for c in found] == [1, 2, 3]
