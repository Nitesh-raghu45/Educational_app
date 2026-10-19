import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Quiz, User
from ..schemas import AttemptCreate, AttemptOut, QuestionResult, QuizOut, QuizQuestionOut
from ..security import current_user
from ..services import quiz as quiz_service

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def quiz_out(quiz: Quiz) -> QuizOut:
    """Questions without answers or explanations; those come back after an attempt."""
    return QuizOut(
        id=quiz.id,
        section_id=quiz.section_id,
        topic=quiz.topic,
        created_at=quiz.created_at,
        questions=[QuizQuestionOut(question=q["question"], options=q["options"]) for q in quiz.questions],
    )


@router.get("/{quiz_id}", response_model=QuizOut)
async def get_quiz(
    quiz_id: uuid.UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> QuizOut:
    return quiz_out(await quiz_service.get_owned_quiz(session, quiz_id, user.id))


@router.post("/{quiz_id}/attempts", response_model=AttemptOut, status_code=201)
async def submit_attempt(
    quiz_id: uuid.UUID,
    body: AttemptCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    quiz = await quiz_service.get_owned_quiz(session, quiz_id, user.id)
    attempt, results = await quiz_service.submit_attempt(session, quiz, user.id, body.answers)
    return AttemptOut(
        id=attempt.id, score=attempt.score, total=attempt.total, results=[QuestionResult(**r) for r in results]
    )
