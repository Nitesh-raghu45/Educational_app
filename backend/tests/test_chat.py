import asyncio
import uuid

from sqlalchemy import update

from app.db import SessionLocal
from app.models import ChatSection
from app.services import sections

from .conftest import parse_sse, register

DOC = (
    "Photosynthesis is the process plants use to turn light energy into chemical energy. "
    "Plants take in carbon dioxide and water and produce glucose and oxygen.\n\n"
    "Cellular respiration releases the energy stored in glucose."
)


async def new_section(client, headers) -> str:
    response = await client.post("/api/v1/sections", json={}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def upload_ready_doc(client, headers, section_id, text=DOC, name="biology.txt") -> str:
    response = await client.post(
        "/api/v1/documents",
        files={"file": (name, text.encode(), "text/plain")},
        data={"section_id": section_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    doc_id = response.json()["id"]
    for _ in range(100):
        status = (await client.get(f"/api/v1/documents/{doc_id}/status", headers=headers)).json()
        if status["status"] in ("ready", "failed"):
            break
        await asyncio.sleep(0.05)
    assert status["status"] == "ready", status
    return doc_id


async def ask(client, headers, section_id, content, key=None):
    body = {"content": content, "client_message_id": key or uuid.uuid4().hex}
    return await client.post(f"/api/v1/sections/{section_id}/messages", json=body, headers=headers)


async def test_question_streams_grounded_answer_with_citations(client):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)

    response = await ask(client, headers, section_id, "What does photosynthesis produce?")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "message_start" and names[-1] == "done"
    assert events[0][1]["section"]["question_count"] == 1
    assert "".join(d["text"] for n, d in events if n == "token") == "Photosynthesis turns light into chemical energy [1]."
    citations = next(d for n, d in events if n == "citations")["citations"]
    assert citations[0]["filename"] == "biology.txt"

    messages = (await client.get(f"/api/v1/sections/{section_id}/messages", headers=headers)).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["status"] == "completed" and messages[1]["citations"]

    section = (await client.get(f"/api/v1/sections/{section_id}", headers=headers)).json()
    assert section["title"] == "What does photosynthesis produce?"
    assert section["remaining"] == 29


async def test_follow_up_sends_history_to_llm(client, fake_llm):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)
    await ask(client, headers, section_id, "What is photosynthesis?")
    await ask(client, headers, section_id, "And what does photosynthesis produce?")
    roles = [m["role"] for m in fake_llm.stream_calls[-1]]
    assert roles == ["system", "user", "assistant", "user"]


async def test_no_evidence_returns_refusal_without_calling_llm(client, fake_llm):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)
    events = parse_sse((await ask(client, headers, section_id, "Explain quantum chromodynamics")).text)
    text = "".join(d["text"] for n, d in events if n == "token")
    assert "couldn't find" in text
    assert fake_llm.stream_calls == []


async def test_question_requires_ready_document(client):
    headers = await register(client)
    section_id = await new_section(client, headers)
    response = await ask(client, headers, section_id, "Hello?")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_READY_DOCUMENTS"
    section = (await client.get(f"/api/v1/sections/{section_id}", headers=headers)).json()
    assert section["question_count"] == 0


async def test_idempotent_resubmission_does_not_use_another_slot(client):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)
    first = parse_sse((await ask(client, headers, section_id, "What is photosynthesis?", key="retry-key-123")).text)
    second = parse_sse((await ask(client, headers, section_id, "What is photosynthesis?", key="retry-key-123")).text)
    assert first[0][1]["assistant_message"]["id"] == second[0][1]["assistant_message"]["id"]
    section = (await client.get(f"/api/v1/sections/{section_id}", headers=headers)).json()
    assert section["question_count"] == 1


async def test_limit_reached_after_max_questions(client):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)
    async with SessionLocal() as session:
        await session.execute(
            update(ChatSection).where(ChatSection.id == uuid.UUID(section_id)).values(question_count=29)
        )
        await session.commit()

    last = parse_sse((await ask(client, headers, section_id, "What is photosynthesis?")).text)
    assert last[0][1]["section"]["status"] == "limit_reached"
    assert last[0][1]["section"]["remaining"] == 0

    response = await ask(client, headers, section_id, "One more?")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SECTION_LIMIT_REACHED"
    section = (await client.get(f"/api/v1/sections/{section_id}", headers=headers)).json()
    assert section["question_count"] == 30

    # History stays readable.
    assert len((await client.get(f"/api/v1/sections/{section_id}/messages", headers=headers)).json()) == 2


async def test_quota_service_never_exceeds_limit(client):
    headers = await register(client)
    section_id = uuid.UUID(await new_section(client, headers))
    await upload_ready_doc(client, headers, str(section_id))
    user_id = uuid.UUID((await client.get("/api/v1/auth/me", headers=headers)).json()["id"])

    accepted = rejected = 0
    for i in range(35):
        async with SessionLocal() as session:
            try:
                await sections.submit_question(
                    session, section_id=section_id, user_id=user_id, content=f"q{i}", idempotency_key=None
                )
                accepted += 1
            except Exception as exc:
                assert getattr(exc, "code", None) == "SECTION_LIMIT_REACHED"
                rejected += 1
    assert (accepted, rejected) == (30, 5)


async def test_retry_failed_answer_keeps_count(client, fake_llm):
    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)

    fake_llm.fail_next_stream = True
    events = parse_sse((await ask(client, headers, section_id, "What is photosynthesis?")).text)
    assert events[-1][0] == "error"
    assistant_id = events[-1][1]["assistant_message_id"]

    events = parse_sse((await client.post(f"/api/v1/sections/{section_id}/retry/{assistant_id}", headers=headers)).text)
    assert events[-1][0] == "done"
    section = (await client.get(f"/api/v1/sections/{section_id}", headers=headers)).json()
    assert section["question_count"] == 1

    # A completed answer cannot be retried.
    response = await client.post(f"/api/v1/sections/{section_id}/retry/{assistant_id}", headers=headers)
    assert response.json()["error"]["code"] == "MESSAGE_NOT_RETRYABLE"


async def test_other_users_cannot_see_or_use_a_section(client):
    owner = await register(client, "owner@example.com")
    intruder = await register(client, "intruder@example.com")
    section_id = await new_section(client, owner)
    for response in (
        await client.get(f"/api/v1/sections/{section_id}", headers=intruder),
        await client.get(f"/api/v1/sections/{section_id}/messages", headers=intruder),
        await ask(client, intruder, section_id, "hi"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SECTION_NOT_FOUND"


async def test_sidebar_lists_most_recent_first(client):
    headers = await register(client)
    first = await new_section(client, headers)
    second = await new_section(client, headers)
    await upload_ready_doc(client, headers, first)
    await ask(client, headers, first, "What is photosynthesis?")
    ids = [s["id"] for s in (await client.get("/api/v1/sections", headers=headers)).json()]
    assert ids == [first, second]
