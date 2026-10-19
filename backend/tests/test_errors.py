from app.services import documents

from .conftest import register

ORIGIN = "http://localhost:5173"


async def test_server_crash_returns_readable_json_with_cors(client, monkeypatch):
    headers = await register(client)

    async def boom(*args, **kwargs):
        raise PermissionError("[Errno 13] Permission denied: '/app/data/uploads'")

    monkeypatch.setattr(documents, "save_upload", boom)
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers={**headers, "Origin": ORIGIN},
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    # Without this header the browser hides the response and the UI can only say "upload failed".
    assert response.headers["access-control-allow-origin"] == ORIGIN


async def test_streaming_answers_still_work_through_error_middleware(client):
    # Regression guard: the middleware must not buffer or break SSE responses.
    from .test_chat import ask, new_section, upload_ready_doc

    headers = await register(client)
    section_id = await new_section(client, headers)
    await upload_ready_doc(client, headers, section_id)
    response = await ask(client, headers, section_id, "What is photosynthesis?")
    assert response.status_code == 200 and "event: done" in response.text
