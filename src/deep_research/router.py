import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette import EventSourceResponse

from deep_research.database import async_session_maker, get_db
from deep_research.models import ResearchSession
from deep_research.schemas import (
    ResearchSessionContinue,
    ResearchSessionCreate,
    ResearchSessionResponse,
)
from deep_research.service import deep_research_service

router = APIRouter()


def _session_to_response(session: ResearchSession) -> ResearchSessionResponse:
    """Преобразует модель сессии в response схему."""
    messages = json.loads(session.messages)
    return ResearchSessionResponse(
        id=session.id,
        status=session.status,
        messages=messages,
        research_task=session.research_task,
        final_report=session.final_report,
    )


@router.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint."""
    return {
        "title": "Deep Research API",
        "description": "API для глубокого исследования",
        "version": "1.0.0",
    }


@router.post("/research", response_model=ResearchSessionResponse, status_code=201)
async def create_research(
    data: ResearchSessionCreate,
    db: AsyncSession = Depends(get_db),
) -> ResearchSessionResponse:
    """Создать новое исследование (без запуска). Используйте /research/{id}/stream для стриминга."""
    session = await deep_research_service.create_research_session(db, data)
    return _session_to_response(session)


@router.get("/research/{research_id}/stream")
async def stream_research(
    research_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Стримит прогресс исследования в реальном времени через SSE."""
    session = await deep_research_service.get_research_session(db, research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия исследования не найдена")

    query = json.loads(session.messages)[0]["content"]

    async def event_generator():
        try:
            async for event in deep_research_service.stream_research(research_id, query):
                if await request.is_disconnected():
                    break
                yield {"event": event.event, "data": json.dumps(event.data, ensure_ascii=False)}

            async with async_session_maker() as finalize_db:
                await deep_research_service.finalize_research_session(finalize_db, research_id)

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


@router.get("/research/{research_id}", response_model=ResearchSessionResponse)
async def get_research(
    research_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResearchSessionResponse:
    """Получить исследование по ID."""
    session = await deep_research_service.get_research_session(db, research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия исследования не найдена")

    return _session_to_response(session)


@router.post("/research/{research_id}/continue", response_model=ResearchSessionResponse)
async def continue_research(
    research_id: int,
    data: ResearchSessionContinue,
    db: AsyncSession = Depends(get_db),
) -> ResearchSessionResponse:
    """Продолжить исследование после ответа на уточняющие вопросы (синхронно)."""
    try:
        session = await deep_research_service.continue_research_session(db, research_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _session_to_response(session)


@router.post("/research/{research_id}/continue/stream")
async def stream_continue_research(
    research_id: int,
    data: ResearchSessionContinue,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Продолжить исследование со стримингом прогресса через SSE."""
    session = await deep_research_service.get_research_session(db, research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия исследования не найдена")

    async def event_generator():
        try:
            async for event in deep_research_service.stream_continue_research(research_id, data.response):
                if await request.is_disconnected():
                    break
                yield {"event": event.event, "data": json.dumps(event.data, ensure_ascii=False)}

            async with async_session_maker() as finalize_db:
                await deep_research_service.finalize_research_session(finalize_db, research_id)

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


@router.get("/research", response_model=list[ResearchSessionResponse])
async def list_research(db: AsyncSession = Depends(get_db)) -> list[ResearchSessionResponse]:
    """Получить список всех исследований."""
    sessions = await deep_research_service.get_all_research_sessions(db)
    return [_session_to_response(session) for session in sessions]
