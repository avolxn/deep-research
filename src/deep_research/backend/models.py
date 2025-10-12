from enum import StrEnum

from sqlalchemy import Enum, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ResearchStatus(StrEnum):
    """Статусы исследования"""

    PENDING = "pending"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""

    pass


class ResearchSession(Base):
    """Модель сессии исследования"""

    __tablename__ = "research_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[ResearchStatus] = mapped_column(Enum(ResearchStatus), default=ResearchStatus.PENDING, nullable=False)
    messages: Mapped[str] = mapped_column(Text, nullable=False)
    research_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_report: Mapped[str | None] = mapped_column(Text, nullable=True)
