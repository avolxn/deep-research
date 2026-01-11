"""Research service — бизнес-логика исследований."""

import asyncio
import logging
import time
from asyncio import Queue
from typing import Any

from langchain_core.messages import HumanMessage

from deep_research.api.schemas import ResearchResponse, ResearchStatus
from deep_research.ml.graph import deep_research_agent

logger = logging.getLogger(__name__)


class EventBuffer:
    """
    Буфер для обработки и фильтрации событий LangGraph.

    Преобразует низкоуровневые события графа в высокоуровневые
    обновления состояния для фронтенда.
    """

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.current_node: str | None = None
        self.last_heartbeat = time.time()
        self.events: list[dict[str, Any]] = []

    def process_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """
        Обработать событие LangGraph и вернуть событие для клиента.

        Returns:
            Событие для отправки клиенту или None если событие нужно пропустить.
        """
        # Обработка событий узлов
        if "langgraph_node" in event.get("metadata", {}):
            node_name = event["metadata"]["langgraph_node"]

            if node_name != self.current_node:
                self.current_node = node_name
                return {
                    "event_type": "node_start",
                    "data": {
                        "node": node_name,
                        "message": self._get_node_message(node_name),
                    },
                }

        # Обработка сообщений
        if "messages" in event:
            messages = event.get("messages", [])
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, "content") and last_message.content:
                    return {
                        "event_type": "message",
                        "data": {
                            "content": last_message.content,
                            "role": getattr(last_message, "type", "unknown"),
                        },
                    }

        # Обработка финального отчёта
        if "final_report" in event and event["final_report"]:
            return {
                "event_type": "report_ready",
                "data": {"report_length": len(event["final_report"])},
            }

        return None

    def _get_node_message(self, node_name: str) -> str:
        """Получить человекочитаемое сообщение для узла."""
        messages = {
            "clarify_with_user": "Анализ запроса...",
            "write_research_task": "Формирование исследовательского задания...",
            "research_supervisor": "Координация исследования...",
            "researcher": "Проведение исследования...",
            "generate_report": "Генерация отчёта...",
        }
        return messages.get(node_name, f"Выполнение: {node_name}")

    def check_heartbeat(self) -> dict[str, Any] | None:
        """Проверить необходимость отправки heartbeat."""
        if time.time() - self.last_heartbeat > 5.0:
            self.last_heartbeat = time.time()
            return {"event_type": "heartbeat", "data": {}}
        return None


class ResearchService:
    """Сервис для проведения исследований."""

    _streams: dict[str, Queue[dict[str, Any] | None]] = {}
    _statuses: dict[str, ResearchStatus] = {}
    _cancellation_flags: dict[str, bool] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def register_stream(cls, thread_id: str, queue: Queue[dict[str, Any] | None]) -> None:
        """Зарегистрировать поток для исследования."""
        async with cls._lock:
            cls._streams[thread_id] = queue
            cls._statuses[thread_id] = ResearchStatus(
                thread_id=thread_id,
                status="pending",
                progress=0.0,
                current_stage="Инициализация",
            )
            cls._cancellation_flags[thread_id] = False

    @classmethod
    async def get_stream(cls, thread_id: str) -> Queue[dict[str, Any] | None] | None:
        """Получить очередь потока по ID."""
        return cls._streams.get(thread_id)

    @classmethod
    async def cleanup_stream(cls, thread_id: str) -> None:
        """Очистить ресурсы потока."""
        async with cls._lock:
            cls._streams.pop(thread_id, None)
            cls._cancellation_flags.pop(thread_id, None)

    @classmethod
    async def get_status(cls, thread_id: str) -> ResearchStatus | None:
        """Получить статус исследования."""
        return cls._statuses.get(thread_id)

    @classmethod
    async def request_cancellation(cls, thread_id: str) -> bool:
        """Запросить отмену исследования."""
        async with cls._lock:
            if thread_id in cls._cancellation_flags:
                cls._cancellation_flags[thread_id] = True
                return True
            return False

    @classmethod
    async def _is_cancelled(cls, thread_id: str) -> bool:
        """Проверить, запрошена ли отмена."""
        return cls._cancellation_flags.get(thread_id, False)

    @classmethod
    async def _update_status(
        cls,
        thread_id: str,
        status: str,
        progress: float = 0.0,
        current_stage: str | None = None,
    ) -> None:
        """Обновить статус исследования."""
        async with cls._lock:
            if thread_id in cls._statuses:
                cls._statuses[thread_id] = ResearchStatus(
                    thread_id=thread_id,
                    status=status,
                    progress=progress,
                    current_stage=current_stage,
                )

    @classmethod
    async def conduct_research(
        cls,
        query: str,
        thread_id: str,
        queue: Queue[dict[str, Any] | None] | None = None,
    ) -> ResearchResponse:
        """
        Провести исследование по заданной теме.

        Args:
            query: Тема исследования
            thread_id: ID потока
            queue: Очередь для отправки событий (для streaming)

        Returns:
            ResearchResponse с результатами исследования
        """
        logger.info(f"Начало исследования [{thread_id}]: {query[:50]}...")
        event_buffer = EventBuffer(thread_id)

        await cls._update_status(thread_id, "running", 0.1, "Запуск исследования")

        async def emit_event(event: dict[str, Any]) -> None:
            if queue:
                await queue.put(event)

        try:
            config = {"configurable": {"thread_id": thread_id}}
            inputs = {"messages": [HumanMessage(content=query)]}

            final_state = None

            async for event in deep_research_agent.astream(inputs, config=config, stream_mode="values"):
                if await cls._is_cancelled(thread_id):
                    logger.info(f"Исследование {thread_id} отменено")
                    await emit_event({"event_type": "cancelled", "data": {"message": "Исследование отменено"}})
                    break

                processed = event_buffer.process_event(event)
                if processed:
                    await emit_event(processed)

                heartbeat = event_buffer.check_heartbeat()
                if heartbeat:
                    await emit_event(heartbeat)

                final_state = event

            if final_state:
                final_report = final_state.get("final_report", "")
                research_task = final_state.get("research_task", "")
                notes = final_state.get("notes", [])

                await cls._update_status(thread_id, "completed", 1.0, "Завершено")

                await emit_event(
                    {
                        "event_type": "complete",
                        "data": {
                            "final_report": final_report,
                            "research_task": research_task,
                            "notes_count": len(notes),
                        },
                    }
                )

                result = ResearchResponse(
                    final_report=final_report,
                    research_task=research_task,
                    sources_count=len(notes),
                    notes=notes,
                    thread_id=thread_id,
                )
            else:
                await cls._update_status(thread_id, "failed", 0.0, "Нет результатов")
                result = ResearchResponse(
                    final_report="Исследование не дало результатов",
                    research_task="",
                    sources_count=0,
                    notes=[],
                    thread_id=thread_id,
                )

        except Exception as e:
            logger.exception(f"Ошибка исследования {thread_id}: {e}")
            await cls._update_status(thread_id, "failed", 0.0, f"Ошибка: {e}")
            await emit_event({"event_type": "error", "data": {"error": str(e)}})

            result = ResearchResponse(
                final_report=f"Ошибка исследования: {e}",
                research_task="",
                sources_count=0,
                notes=[],
                thread_id=thread_id,
            )

        finally:
            if queue:
                await queue.put(None)

        return result
