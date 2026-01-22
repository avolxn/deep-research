"""Research service for conducting deep research."""

import logging
import uuid
from asyncio import Queue

from langchain_core.messages import HumanMessage

from deep_research.ml.graph import deep_research_agent

logger = logging.getLogger(__name__)


class ResearchSession:
    """Represents an active research session."""

    def __init__(self, session_id: str, query: str):
        self.session_id = session_id
        self.query = query
        self.queue = Queue()
        self.thread_config = {"configurable": {"thread_id": session_id}}
        self.is_active = True
        self.todo_manager = None

    async def send_event(self, event_type: str, data: dict):
        """Send an event to the stream."""
        await self.queue.put({"event_type": event_type, "data": data})

    async def close(self):
        """Close the session."""
        self.is_active = False
        await self.queue.put(None)


class ResearchService:
    """Service for managing research sessions."""

    _sessions: dict[str, ResearchSession] = {}

    @classmethod
    def create_session(cls, query: str) -> ResearchSession:
        """Create a new research session."""
        session_id = str(uuid.uuid4())
        session = ResearchSession(session_id, query)
        cls._sessions[session_id] = session
        logger.info(f"Created session {session_id}")
        return session

    @classmethod
    def get_session(cls, session_id: str) -> ResearchSession | None:
        """Get an existing session."""
        return cls._sessions.get(session_id)

    @classmethod
    def remove_session(cls, session_id: str):
        """Remove a session."""
        if session_id in cls._sessions:
            del cls._sessions[session_id]
            logger.info(f"Removed session {session_id}")

    @classmethod
    async def start_research(cls, session: ResearchSession):
        """Start research for a session."""
        should_close = True
        try:
            await session.send_event(
                "research_started",
                {
                    "query": session.query,
                    "session_id": session.session_id,
                },
            )

            async for chunk in deep_research_agent.astream(
                {"messages": [HumanMessage(content=session.query)]},
                config=session.thread_config,
                stream_mode="updates",
            ):
                if not session.is_active:
                    logger.info(f"Session {session.session_id} cancelled")
                    break

                for node_name, state_update in chunk.items():
                    await cls._handle_node_update(session, node_name, state_update)

            state_snapshot = await deep_research_agent.aget_state(session.thread_config)
            should_close = await cls._handle_completion(session, state_snapshot.values)

        except Exception as e:
            logger.error(f"Error in session {session.session_id}: {e}", exc_info=True)
            await session.send_event("error", {"error": str(e)})
        finally:
            if should_close:
                await session.close()
                cls.remove_session(session.session_id)
            if should_close:
                await session.close()
                cls.remove_session(session.session_id)

    @classmethod
    async def continue_research(cls, session: ResearchSession, message: str):
        """Continue research after clarification."""
        should_close = True
        try:
            await session.send_event(
                "research_continued",
                {
                    "message_received": message,
                },
            )

            async for chunk in deep_research_agent.astream(
                {"messages": [HumanMessage(content=message)]},
                config=session.thread_config,
                stream_mode="updates",
            ):
                if not session.is_active:
                    break

                for node_name, state_update in chunk.items():
                    await cls._handle_node_update(session, node_name, state_update)

            state_snapshot = await deep_research_agent.aget_state(session.thread_config)
            should_close = await cls._handle_completion(session, state_snapshot.values)

        except Exception as e:
            logger.error(f"Error continuing session {session.session_id}: {e}", exc_info=True)
            await session.send_event("error", {"error": str(e)})
        finally:
            if should_close:
                await session.close()
                cls.remove_session(session.session_id)

    @classmethod
    async def _handle_node_update(cls, session: ResearchSession, node_name: str, state_update: dict | None):
        """Handle updates from a graph node."""
        await session.send_event("node_started", {"node": node_name})

        if state_update is None:
            state_update = {}

        if node_name == "write_research_brief":
            session.todo_manager = state_update.get("todo_manager")
            research_brief = state_update.get("research_brief", "")
            await session.send_event(
                "research_brief_created",
                {
                    "research_brief": research_brief,
                },
            )

        if node_name == "execute_tasks":
            notes = state_update.get("notes", [])
            if notes:
                await session.send_event(
                    "task_results",
                    {
                        "results_count": len(notes),
                        "latest_result": notes[-1][:500] if notes else "",
                    },
                )

        if node_name in ["plan_research", "execute_tasks", "process_results", "reflect_on_tasks"]:
            await cls._send_research_progress(session, node_name, state_update)

        await session.send_event("node_completed", {"node": node_name})

    @classmethod
    async def _send_research_progress(cls, session: ResearchSession, node_name: str, state_update: dict):
        """Send research progress updates."""
        todo_manager = state_update.get("todo_manager") or session.todo_manager
        if not todo_manager:
            return

        pending = todo_manager.get_pending_tasks()
        completed = todo_manager.get_completed_tasks()
        iterations = state_update.get("research_iterations", 0)

        await session.send_event(
            "research_progress",
            {
                "node": node_name,
                "pending_tasks": len(pending),
                "completed_tasks": len(completed),
                "research_iterations": iterations,
            },
        )

    @classmethod
    async def _handle_completion(cls, session: ResearchSession, final_state: dict) -> bool:
        """Handle graph completion.

        Returns:
            True if session should be closed, False if waiting for clarification
        """
        logger.info(f"Handling completion for session {session.session_id}")
        logger.info(f"Final state keys: {list(final_state.keys())}")
        logger.info(f"Has final_report: {bool(final_state.get('final_report'))}")

        if not final_state.get("final_report"):
            messages = final_state.get("messages", [])
            logger.info(f"No final_report. Messages count: {len(messages)}")
            if messages and hasattr(messages[-1], "content"):
                questions = messages[-1].content
                logger.info(
                    f"Clarification needed. Questions: {questions[:100] if len(questions) > 100 else questions}"
                )
                await session.send_event(
                    "clarification_needed",
                    {
                        "questions": questions,
                        "session_id": session.session_id,
                    },
                )
                logger.info(f"Session {session.session_id} kept alive for clarification")
                return False
            else:
                logger.warning("No messages or last message has no content")

        final_report = final_state.get("final_report", "")
        iterations = final_state.get("research_iterations", 0)

        logger.info(f"Research complete for session {session.session_id}")

        await session.send_event(
            "research_complete",
            {
                "final_report": final_report,
                "research_iterations": iterations,
            },
        )
        return True
