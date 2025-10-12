import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from deep_research.backend.database import get_db
from deep_research.backend.schemas import (
    ResearchSessionContinue,
    ResearchSessionCreate,
    ResearchSessionResponse,
)
from deep_research.backend.service import deep_research_service
from deep_research.config import settings

router = APIRouter()


@router.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint

    Returns:
        dict[str, Any]: Информация о API
    """
    return {
        "title": settings.API.TITLE,
        "description": settings.API.DESCRIPTION,
        "version": settings.API.VERSION,
    }


@router.post("/research", response_model=ResearchSessionResponse, status_code=201)
async def create_research(
    data: ResearchSessionCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchSessionResponse:
    """Создать новое исследование

    Args:
        data (ResearchSessionCreate): Данные для создания исследования
        db (AsyncSession): Сессия базы данных

    Returns:
        ResearchSessionResponse: Созданная сессия исследования
    """
    session = await deep_research_service.create_research_session(db, data)
    messages = json.loads(session.messages)

    return ResearchSessionResponse(
        id=session.id,
        status=session.status,
        messages=messages,
        research_brief=session.research_brief,
        final_report=session.final_report,
    )


@router.get("/research/{research_id}", response_model=ResearchSessionResponse)
async def get_research(
    research_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchSessionResponse:
    """Получить исследование по ID

    Args:
        research_id (int): ID сессии
        db (AsyncSession): Сессия базы данных

    Returns:
        ResearchSessionResponse: Данные сессии исследования
    """

    session = await deep_research_service.get_research_session(db, research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия исследования не найдена")

    messages = json.loads(session.messages)

    return ResearchSessionResponse(
        id=session.id,
        status=session.status,
        messages=messages,
        research_brief=session.research_brief,
        final_report=session.final_report,
    )


@router.post("/research/{research_id}/continue", response_model=ResearchSessionResponse)
async def continue_research(
    research_id: int,
    data: ResearchSessionContinue,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResearchSessionResponse:
    """Продолжить исследование после ответа на уточняющие вопросы

    Args:
        research_id (int): ID сессии
        data (ResearchSessionContinue): Ответ пользователя
        db (AsyncSession): Сессия базы данных

    Returns:
        ResearchSessionResponse: Обновленная сессия исследования
    """

    try:
        session = await deep_research_service.continue_research_session(db, research_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    messages = json.loads(session.messages)

    return ResearchSessionResponse(
        id=session.id,
        status=session.status,
        messages=messages,
        research_brief=session.research_brief,
        final_report=session.final_report,
    )


@router.get("/research", response_model=list[ResearchSessionResponse])
async def list_research(db: AsyncSession = Depends(get_db)) -> list[ResearchSessionResponse]:  # noqa: B008
    """Получить список всех исследований

    Args:
        db (AsyncSession): Сессия базы данных

    Returns:
        list[ResearchSessionResponse]: Список сессий исследования
    """

    sessions = await deep_research_service.get_all_research_sessions(db)
    result = []

    for session in sessions:
        messages = json.loads(session.messages)

        result.append(
            ResearchSessionResponse(
                id=session.id,
                status=session.status,
                messages=messages,
                research_brief=session.research_brief,
                final_report=session.final_report,
            )
        )

    return result
