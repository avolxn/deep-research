import json
import logging

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deep_research.agent import deep_research_agent
from deep_research.models import ResearchSession, ResearchStatus
from deep_research.schemas import ResearchSessionContinue, ResearchSessionCreate

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class DeepResearchService:
    def __init__(self) -> None:
        self.deep_research_agent = deep_research_agent

    def _extract_messages_history(self, messages: list[AnyMessage]) -> list[dict[str, str]]:
        """Извлекает историю сообщений в формате для БД."""
        history = []
        for message in messages:
            if isinstance(message, HumanMessage):
                history.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage) and message.content:
                history.append({"role": "assistant", "content": message.content})
            elif isinstance(message, ToolMessage) and message.content:
                tool_name = getattr(message, "name", "tool")
                history.append({"role": "assistant", "content": f"[{tool_name}]\n{message.content}"})
        return history

    async def create_research_session(
        self,
        db: AsyncSession,
        data: ResearchSessionCreate,
    ) -> ResearchSession:
        """Создает новую сессию исследования (без запуска агента)."""
        session = ResearchSession(
            status=ResearchStatus.PENDING,
            messages=json.dumps([{"role": "user", "content": data.query}]),
            research_task=None,
            final_report=None,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def continue_research_session(
        self,
        db: AsyncSession,
        session_id: int,
        data: ResearchSessionContinue,
    ) -> ResearchSession:
        """Продолжает исследование после ответа пользователя на уточняющие вопросы."""
        session = await self.get_research_session(db, session_id)

        if not session:
            raise ValueError(f"Сессия с ID {session_id} не найдена")

        if session.status != ResearchStatus.AWAITING_CLARIFICATION:
            raise ValueError(f"Сессия не ожидает уточнения. Текущий статус: {session.status}")

        thread_id = str(session.id)
        config = {"configurable": {"thread_id": thread_id}}

        session.status = ResearchStatus.IN_PROGRESS

        result = await self.deep_research_agent.ainvoke(
            {"messages": [HumanMessage(content=data.response)]},
            config=config,
        )

        messages = result["messages"]
        session.messages = json.dumps(self._extract_messages_history(messages))

        if result.get("final_report"):
            session.status = ResearchStatus.COMPLETED
            session.research_task = result.get("research_task")
            session.final_report = result["final_report"]
        elif result.get("research_task"):
            session.status = ResearchStatus.IN_PROGRESS
            session.research_task = result["research_task"]
        else:
            session.status = ResearchStatus.AWAITING_CLARIFICATION

        await db.commit()
        await db.refresh(session)
        return session

    async def get_research_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> ResearchSession | None:
        """Получает сессию исследования по ID."""
        result = await db.execute(select(ResearchSession).where(ResearchSession.id == session_id))
        return result.scalar_one_or_none()

    async def get_all_research_sessions(self, db: AsyncSession) -> list[ResearchSession]:
        """Получает все сессии исследований"""
        result = await db.execute(select(ResearchSession).order_by(ResearchSession.id.desc()))
        return list(result.scalars().all())


deep_research_service = DeepResearchService()
