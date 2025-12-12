import operator
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState, add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class WebSummary(BaseModel):
    """Резюме исследования с ключевыми выводами."""

    summary: str = Field(
        description="Краткое содержание (абзацы и/или пункты)",
    )
    key_excerpts: str = Field(
        description="Цитата 1, цитата 2, цитата 3 ... максимум 5 цитат",
    )


class ClarifyWithUser(BaseModel):
    """Модель для запросов на уточнение у пользователя."""

    need_clarification: bool = Field(
        description="Нужно ли уточнить у пользователя какие-то моменты?",
    )
    questions: str = Field(
        description="Уточняющие вопросы, которые нужно задать пользователю",
    )
    verification: str = Field(
        description="Краткое подтверждение, что информации достаточно и приступаем к исследованию",
    )


research_question_description = """Детальное исследовательское задание (НЕ заголовок, а полноценный текст минимум на 200 слов).

ОБЯЗАТЕЛЬНО включи:
1. ТЕМА: Чёткая формулировка темы исследования (1-2 предложения)
2. НАПРАВЛЕНИЯ: 3-5 конкретных направлений для изучения, каждое с описанием в 2-3 предложения
3. КОНТЕКСТ: Временные рамки, географический фокус, целевая аудитория (если применимо)
4. ИСТОЧНИКИ: Какие типы источников приоритетны (научные статьи, новости, официальные отчёты и т.д.)
5. ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Что должно быть в финальном отчёте

Пиши развёрнуто, как техническое задание для исследователя."""


class ResearchQuestion(BaseModel):
    """Исследовательское задание для направления исследования."""

    research_task: str = Field(description=research_question_description)


class DeepResearchState(MessagesState):
    """Основное состояние агента, содержащее сообщения и данные исследования."""

    supervisor_messages: Annotated[list[AnyMessage], add_messages]
    research_task: str
    raw_notes: Annotated[list[str], operator.add]
    notes: Annotated[list[str], operator.add]
    final_report: str


class SupervisorState(TypedDict):
    """Состояние супервизора, управляющего исследовательскими задачами."""

    supervisor_messages: Annotated[list[AnyMessage], add_messages]
    research_task: str
    notes: Annotated[list[str], operator.add]
    raw_notes: Annotated[list[str], operator.add]
    research_iterations: int


class ResearcherState(TypedDict):
    """Состояние отдельных исследователей, проводящих исследование."""

    researcher_messages: Annotated[list[AnyMessage], add_messages]
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], operator.add]
    tool_call_iterations: int


class ResearcherOutputState(TypedDict):
    """Выходное состояние от отдельных исследователей."""

    compressed_research: str
    raw_notes: list[str]
