from pydantic import BaseModel

from deep_research.backend.models import ResearchStatus


class ResearchSessionCreate(BaseModel):
    """Создание новой сессии исследования"""

    query: str


class ResearchSessionContinue(BaseModel):
    """Продолжение сессии с ответом пользователя на уточняющие вопросы"""

    response: str


class ResearchSessionResponse(BaseModel):
    """Ответ с данными сессии исследования"""

    id: int
    status: ResearchStatus
    messages: list[dict[str, str]]
    research_brief: str | None = None
    final_report: str | None = None
