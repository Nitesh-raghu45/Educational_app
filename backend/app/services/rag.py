"""Grounded answer generation: history -> query rewrite -> retrieval -> evidence check -> streamed answer.

Runs in its own DB session as a background task, so the answer is still saved if the browser
disconnects mid-stream. Events go to `emit`, which the SSE endpoint forwards to the client.
"""

import logging
import re
import uuid
from typing import Any, Awaitable, Callable

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import SessionLocal
from ..models import ChatMessage, ChatSection, utcnow
from . import conversation, providers
from .retrieval import Evidence, retrieve
from .sections import ready_document_ids

logger = logging.getLogger(__name__)

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]

SYSTEM_PROMPT = """You are a study assistant. Answer the student's question using ONLY the numbered SOURCES, which come from documents the student uploaded.

Rules:
- Cite every factual statement inline, right after it, with its source number in plain square brackets, e.g. [1] or [2][3].
- If the SOURCES do not contain the answer, say clearly that you could not find it in the uploaded documents. Never fill gaps with outside knowledge.
- Earlier conversation is only for understanding what the student means; it is not evidence.
- Be clear and concise. Use Markdown (short lists, bold key terms) when it helps understanding."""

NOT_FOUND_ANSWER = (
    "I couldn't find anything about that in the documents attached to this chat. "
    "Try rephrasing the question, or upload/attach the material that covers it."
)

# gpt-oss models sometimes cite as 【1】 or 【1†source】 instead of [1]; accept all of them.
_CITATION_RE = re.compile(r"[\[【](\d{1,2})(?:†[^\]】]*)?[\]】]")


def build_messages(
    summary: str | None, history: list[ChatMessage], evidence: list[Evidence], question: str, query: str
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if summary:
        messages.append({"role": "system", "content": f"Summary of the earlier conversation:\n{summary}"})
    messages.extend(conversation.history_as_chat(history))
    sources = "\n\n".join(
        f"[{i}] ({e.filename}{f', page {e.page}' if e.page else ''})\n{e.text}" for i, e in enumerate(evidence, 1)
    )
    interpretation = f"\n(Interpreted as: {query})" if query != question else ""
    messages.append({"role": "user", "content": f"SOURCES:\n{sources}\n\nQUESTION: {question}{interpretation}"})
    return messages


def extract_citations(answer: str, evidence: list[Evidence]) -> list[dict[str, Any]]:
    used: list[int] = []
    for match in _CITATION_RE.finditer(answer):
        n = int(match.group(1))
        if 1 <= n <= len(evidence) and n not in used:
            used.append(n)
    return [evidence[n - 1].citation(index=n) for n in used]


async def generate_answer(assistant_message_id: uuid.UUID, emit: Emit) -> None:
    async with SessionLocal() as session:
        try:
            await _generate(session, assistant_message_id, emit)
        except Exception as exc:
            logger.exception("Answer generation failed for %s", assistant_message_id)
            await session.rollback()
            await session.execute(
                update(ChatMessage)
                .where(ChatMessage.id == assistant_message_id)
                .values(status="failed", error=str(exc)[:1000], updated_at=utcnow())
            )
            await session.commit()
            await emit(
                "error",
                {
                    "code": "GENERATION_FAILED",
                    "message": "The answer could not be generated. Retrying won't use another question.",
                    "assistant_message_id": str(assistant_message_id),
                },
            )


async def _generate(session: AsyncSession, assistant_message_id: uuid.UUID, emit: Emit) -> None:
    settings = get_settings()
    assistant = await session.get(ChatMessage, assistant_message_id)
    if assistant is None or assistant.reply_to_id is None:
        raise RuntimeError("assistant message not found")
    question_message = await session.get(ChatMessage, assistant.reply_to_id)
    section = await session.get(ChatSection, assistant.section_id)
    if question_message is None or section is None:
        raise RuntimeError("question or section not found")
    question = question_message.content

    assistant.status = "streaming"
    assistant.updated_at = utcnow()
    await session.commit()

    history = await conversation.recent_history(
        session, section.id, before=question_message.created_at, limit=settings.history_window
    )
    query = await conversation.rewrite_query(section.summary, history, question)
    evidence = await retrieve(
        session,
        user_id=section.user_id,
        document_ids=await ready_document_ids(session, section.id),
        query=query,
        top_k=settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
    )

    if not evidence:
        # No supporting evidence: answer with a fixed refusal instead of letting the model guess.
        answer, citations = NOT_FOUND_ANSWER, []
        await emit("token", {"text": answer})
    else:
        parts: list[str] = []
        messages = build_messages(section.summary, history, evidence, question, query)
        async for delta in providers.llm().stream(messages, model=settings.groq_answer_model):
            parts.append(delta)
            await emit("token", {"text": delta})
        answer = "".join(parts).strip() or NOT_FOUND_ANSWER
        citations = extract_citations(answer, evidence)

    assistant.content = answer
    assistant.citations = citations
    assistant.status = "completed"
    assistant.updated_at = utcnow()
    await session.commit()
    await emit("citations", {"citations": citations})
    await emit("done", {"assistant_message_id": str(assistant.id), "status": "completed"})

    try:
        await conversation.update_summary(session, section)
    except Exception:
        logger.warning("Summary update failed for section %s", section.id, exc_info=True)
        await session.rollback()
