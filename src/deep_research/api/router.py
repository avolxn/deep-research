"""API routes for Deep Research."""

import asyncio
import json
import logging
import time
import uuid
from asyncio import Queue
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from deep_research.api.schemas import (
    ErrorResponse,
    ResearchRequest,
    ResearchResponse,
    ResearchStatus,
    StreamResponse,
)
from deep_research.api.service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["Research"])


@router.post(
    "",
    response_model=ResearchResponse | StreamResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Запустить исследование",
    description="Запускает глубокое исследование по заданной теме",
)
async def create_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
) -> ResearchResponse | StreamResponse:
    """
    Запустить исследование по теме.

    При streaming=True возвращает URL для подключения к потоку событий.
    При streaming=False выполняет исследование синхронно и возвращает результат.
    """
    logger.info(f"Получен запрос на исследование: {request.query[:50]}...")

    thread_id = request.thread_id or str(uuid.uuid4())

    if request.streaming:
        queue: Queue[dict[str, Any] | None] = Queue()
        await ResearchService.register_stream(thread_id, queue)

        background_tasks.add_task(
            ResearchService.conduct_research,
            query=request.query,
            thread_id=thread_id,
            queue=queue,
        )

        return StreamResponse(
            stream_url=f"/api/research/stream/{thread_id}",
            message="Исследование запущено. Подключитесь к stream_url для получения обновлений.",
            thread_id=thread_id,
        )

    # Синхронное выполнение
    try:
        result = await ResearchService.conduct_research(
            query=request.query,
            thread_id=thread_id,
            queue=None,
        )
        return result
    except Exception as e:
        logger.exception(f"Ошибка исследования: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/stream/{thread_id}",
    summary="Поток событий исследования",
    description="SSE endpoint для получения событий исследования в реальном времени",
)
async def stream_research(thread_id: str, request: Request) -> EventSourceResponse:
    """Поток событий исследования через Server-Sent Events."""
    logger.info(f"Подключение к потоку {thread_id}")

    queue = await ResearchService.get_stream(thread_id)
    if not queue:
        raise HTTPException(status_code=404, detail=f"Поток {thread_id} не найден")

    async def event_generator():
        heartbeat_interval = 5.0
        last_heartbeat = time.time()

        try:
            # Отправляем событие подключения
            yield {
                "event": "connected",
                "data": json.dumps({"event_type": "connected", "data": {"thread_id": thread_id}}),
            }

            while True:
                if await request.is_disconnected():
                    logger.info(f"Клиент отключился от потока {thread_id}")
                    break

                current_time = time.time()
                timeout = min(heartbeat_interval, heartbeat_interval - (current_time - last_heartbeat))

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=max(0.1, timeout))

                    # None — сигнал завершения
                    if event is None:
                        logger.info(f"Поток {thread_id} завершён")
                        yield {
                            "event": "complete",
                            "data": json.dumps({"event_type": "complete", "data": {}}),
                        }
                        break

                    event_type = event.get("event_type", "update")
                    yield {"event": event_type, "data": json.dumps(event)}

                except TimeoutError:
                    if time.time() - last_heartbeat >= heartbeat_interval:
                        yield {
                            "event": "heartbeat",
                            "data": json.dumps({"event_type": "heartbeat", "data": {}}),
                        }
                        last_heartbeat = time.time()

        except asyncio.CancelledError:
            logger.info(f"Генератор событий {thread_id} отменён")
        except Exception as e:
            logger.exception(f"Ошибка в генераторе событий {thread_id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"event_type": "error", "data": {"error": str(e)}}),
            }
        finally:
            await ResearchService.cleanup_stream(thread_id)

    return EventSourceResponse(event_generator())


@router.get(
    "/status/{thread_id}",
    response_model=ResearchStatus,
    responses={404: {"model": ErrorResponse}},
    summary="Статус исследования",
    description="Получить текущий статус исследования",
)
async def get_research_status(thread_id: str) -> ResearchStatus:
    """Получить статус исследования по thread_id."""
    status = await ResearchService.get_status(thread_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Исследование {thread_id} не найдено")
    return status


@router.post(
    "/stop/{thread_id}",
    summary="Остановить исследование",
    description="Запросить остановку активного исследования",
)
async def stop_research(thread_id: str) -> dict[str, str]:
    """Остановить активное исследование."""
    logger.info(f"Запрос на остановку исследования {thread_id}")

    success = await ResearchService.request_cancellation(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Исследование {thread_id} не найдено")

    return {
        "status": "cancellation_requested",
        "thread_id": thread_id,
        "message": "Запрос на остановку отправлен",
    }


@router.get(
    "/health",
    summary="Проверка здоровья API",
    description="Проверить работоспособность API исследований",
)
async def health_check() -> dict[str, str]:
    """Проверка здоровья API."""
    return {"status": "healthy", "service": "deep-research"}
