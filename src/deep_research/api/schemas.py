"""Pydantic schemas for Deep Research API."""

from typing import Any

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Модель запроса на исследование."""

    query: str = Field(..., description="Тема или вопрос для исследования")
    streaming: bool = Field(default=False, description="Включить потоковую передачу событий")
    thread_id: str | None = Field(default=None, description="ID потока для продолжения диалога")


class ResearchResponse(BaseModel):
    """Модель ответа исследования."""

    final_report: str = Field(..., description="Финальный отчёт исследования")
    research_task: str = Field(default="", description="Сформулированное исследовательское задание")
    sources_count: int = Field(default=0, description="Количество использованных источников")
    notes: list[str] = Field(default_factory=list, description="Заметки исследования")
    thread_id: str = Field(..., description="ID потока для продолжения диалога")


class ResearchEvent(BaseModel):
    """Модель события при потоковой передаче."""

    event_type: str = Field(..., description="Тип события")
    data: dict[str, Any] = Field(default_factory=dict, description="Данные события")


class StreamResponse(BaseModel):
    """Модель ответа для потоковой передачи."""

    stream_url: str = Field(..., description="URL для подключения к потоку событий")
    message: str = Field(..., description="Статусное сообщение")
    thread_id: str = Field(..., description="ID потока исследования")


class ResearchStatus(BaseModel):
    """Модель статуса исследования."""

    thread_id: str = Field(..., description="ID потока")
    status: str = Field(..., description="Статус: pending, running, completed, failed")
    progress: float = Field(default=0.0, description="Прогресс от 0 до 1")
    current_stage: str | None = Field(default=None, description="Текущий этап исследования")


class ErrorResponse(BaseModel):
    """Модель ответа с ошибкой."""

    detail: str = Field(..., description="Описание ошибки")
    error_code: str | None = Field(default=None, description="Код ошибки")
