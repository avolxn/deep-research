from operator import add
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

# Structured outputs


class ClarifyWithUser(BaseModel):
    """Модель для запросов на уточнение у пользователя"""

    need_clarification: bool = Field(
        description="Нужно ли уточнить у пользователя какие-то моменты?",
    )
    questions: str = Field(
        description="Уточняющие вопросы, которые нужно задать пользователю. Максимум 3 вопроса",
    )
    verification: str = Field(
        "Краткое подтверждение, что информации достаточно, 1–2 строки с пониманием запроса и что приступаешь к исследованию сейчас",
    )


class WebSummary(BaseModel):
    """Резюме исследования с ключевыми выводами"""

    summary: str = Field(
        description="Краткое содержание (абзацы и/или пункты)",
    )
    key_excerpts: str = Field(
        description="Цитата 1, цитата 2, цитата 3 ... максимум 5 цитат. Дополнительные выдержки при необходимости",
    )


# States


class DeepResearchState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    research_brief: str
    raw_notes: Annotated[list[str], add]
    notes: Annotated[list[str], add]
    final_report: str


class SupervisorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    research_brief: str
    raw_notes: Annotated[list[str], add]
    notes: Annotated[list[str], add]


class ResearcherState(TypedDict):
    researcher_messages: Annotated[list[AnyMessage], add_messages]
    raw_notes: Annotated[list[str], add]
    compressed_research: str
