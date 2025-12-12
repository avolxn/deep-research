import json
import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deep_research.agent import deep_research_agent
from deep_research.models import ResearchSession, ResearchStatus
from deep_research.schemas import ResearchSessionContinue, ResearchSessionCreate, StreamEvent, StreamEventType

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

    async def stream_research(
        self,
        session_id: int,
        query: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Стримит прогресс исследования через astream."""
        thread_id = str(session_id)
        config = {"configurable": {"thread_id": thread_id}}

        yield StreamEvent(
            event=StreamEventType.STATUS,
            data={"status": ResearchStatus.IN_PROGRESS, "message": "Начинаем исследование..."},
        )

        try:
            logger.info(f"Starting research stream for session {session_id}")
            async for namespace, chunk in self.deep_research_agent.astream(
                {"messages": [HumanMessage(content=query)]},
                config=config,
                stream_mode="updates",
                subgraphs=True,
            ):
                logger.debug(f"Received chunk from {namespace}: {chunk}")
                for node_name, node_output in chunk.items():
                    if node_output is None:
                        continue
                    logger.info(f"Processing node: {node_name} (namespace: {namespace})")
                    if node_name == "clarify_with_user":
                        messages = node_output.get("messages", [])
                        if messages:
                            last_message = messages[-1]
                            if isinstance(last_message, AIMessage) and last_message.content:
                                yield StreamEvent(
                                    event=StreamEventType.CLARIFICATION,
                                    data={"content": last_message.content},
                                )

                    elif node_name == "write_research_task":
                        research_task = node_output.get("research_task", "")
                        if research_task:
                            yield StreamEvent(
                                event=StreamEventType.STATUS,
                                data={"status": ResearchStatus.IN_PROGRESS, "research_task": research_task},
                            )

                    elif node_name == "research_supervisor":
                        notes = node_output.get("notes", [])
                        raw_notes = node_output.get("raw_notes", [])

                        if raw_notes:
                            for note in raw_notes:
                                yield StreamEvent(
                                    event=StreamEventType.RESEARCH_RESULT,
                                    data={"compressed_research": note[:500] + "..." if len(note) > 500 else note},
                                )

                        if notes:
                            for note in notes:
                                yield StreamEvent(
                                    event=StreamEventType.RESEARCH_RESULT,
                                    data={"note": note[:500] + "..." if len(note) > 500 else note},
                                )

                    elif node_name == "generate_report":
                        final_report = node_output.get("final_report", "")
                        if final_report:
                            yield StreamEvent(
                                event=StreamEventType.REPORT,
                                data={"final_report": final_report},
                            )

                    # События из подграфов исследователей
                    elif node_name == "compress_research":
                        compressed = node_output.get("compressed_research", "")
                        if compressed:
                            yield StreamEvent(
                                event=StreamEventType.RESEARCH_RESULT,
                                data={
                                    "compressed_research": compressed[:500] + "..."
                                    if len(compressed) > 500
                                    else compressed
                                },
                            )

                    elif node_name == "researcher":
                        research_topic = node_output.get("research_topic", "")
                        if research_topic:
                            yield StreamEvent(
                                event=StreamEventType.RESEARCH_TOPIC,
                                data={"topic": research_topic[:200]},
                            )

            yield StreamEvent(
                event=StreamEventType.DONE,
                data={"message": "Исследование завершено"},
            )

        except Exception as e:
            logger.exception(f"Error in stream_research: {e}")
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"error": str(e)},
            )

    async def finalize_research_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> ResearchSession | None:
        """Финализирует сессию после стриминга, получая финальное состояние из checkpointer."""
        session = await self.get_research_session(db, session_id)
        if not session:
            return None

        thread_id = str(session_id)
        config = {"configurable": {"thread_id": thread_id}}

        state = await self.deep_research_agent.aget_state(config)
        if state and state.values:
            messages = state.values.get("messages", [])
            session.messages = json.dumps(self._extract_messages_history(messages))

            if state.values.get("final_report"):
                session.status = ResearchStatus.COMPLETED
                session.research_task = state.values.get("research_task")
                session.final_report = state.values["final_report"]
            elif state.values.get("research_task"):
                session.status = ResearchStatus.IN_PROGRESS
                session.research_task = state.values["research_task"]
            else:
                session.status = ResearchStatus.AWAITING_CLARIFICATION

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

    async def stream_continue_research(
        self,
        session_id: int,
        response: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Стримит продолжение исследования после ответа пользователя."""
        thread_id = str(session_id)
        config = {"configurable": {"thread_id": thread_id}}

        yield StreamEvent(
            event=StreamEventType.STATUS,
            data={"status": ResearchStatus.IN_PROGRESS, "message": "Продолжаем исследование..."},
        )

        try:
            async for namespace, chunk in self.deep_research_agent.astream(
                {"messages": [HumanMessage(content=response)]},
                config=config,
                stream_mode="updates",
                subgraphs=True,
            ):
                for node_name, node_output in chunk.items():
                    if node_name == "clarify_with_user":
                        messages = node_output.get("messages", [])
                        if messages:
                            last_message = messages[-1]
                            if isinstance(last_message, AIMessage) and last_message.content:
                                yield StreamEvent(
                                    event=StreamEventType.CLARIFICATION,
                                    data={"content": last_message.content},
                                )

                    elif node_name == "write_research_task":
                        research_task = node_output.get("research_task", "")
                        if research_task:
                            yield StreamEvent(
                                event=StreamEventType.STATUS,
                                data={"status": ResearchStatus.IN_PROGRESS, "research_task": research_task},
                            )

                    elif node_name == "research_supervisor":
                        notes = node_output.get("notes", [])
                        raw_notes = node_output.get("raw_notes", [])

                        if raw_notes:
                            for note in raw_notes:
                                yield StreamEvent(
                                    event=StreamEventType.RESEARCH_RESULT,
                                    data={"compressed_research": note[:500] + "..." if len(note) > 500 else note},
                                )

                        if notes:
                            for note in notes:
                                yield StreamEvent(
                                    event=StreamEventType.RESEARCH_RESULT,
                                    data={"note": note[:500] + "..." if len(note) > 500 else note},
                                )

                    elif node_name == "generate_report":
                        final_report = node_output.get("final_report", "")
                        if final_report:
                            yield StreamEvent(
                                event=StreamEventType.REPORT,
                                data={"final_report": final_report},
                            )

                    elif node_name == "compress_research":
                        compressed = node_output.get("compressed_research", "")
                        if compressed:
                            yield StreamEvent(
                                event=StreamEventType.RESEARCH_RESULT,
                                data={
                                    "compressed_research": compressed[:500] + "..."
                                    if len(compressed) > 500
                                    else compressed
                                },
                            )

                    elif node_name == "researcher":
                        research_topic = node_output.get("research_topic", "")
                        if research_topic:
                            yield StreamEvent(
                                event=StreamEventType.RESEARCH_TOPIC,
                                data={"topic": research_topic[:200]},
                            )

            yield StreamEvent(
                event=StreamEventType.DONE,
                data={"message": "Исследование завершено"},
            )

        except Exception as e:
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"error": str(e)},
            )

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
