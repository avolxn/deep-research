"""API router for deep research endpoints."""

import asyncio
import datetime
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from deep_research.api.schemas import (
    MessageRequest,
    MessageResponse,
    ResearchRequest,
    ResearchResponse,
)
from deep_research.api.service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Research"])


@router.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks) -> ResearchResponse:
    """Start a new research session.

    Returns a session_id and stream_url. Connect to the stream_url to receive real-time updates.
    """
    logger.info(f"Starting research: {request.query[:100]}")

    session = ResearchService.create_session(request.query)

    background_tasks.add_task(ResearchService.start_research, session)

    return ResearchResponse(
        session_id=session.session_id,
        stream_url=f"/stream/{session.session_id}",
        message="Research started. Connect to stream_url for updates.",
    )


@router.get("/stream/{session_id}")
async def stream_research(session_id: str, request: Request) -> EventSourceResponse:
    """Stream research updates via Server-Sent Events."""
    logger.info(f"Client connecting to session {session_id}")

    session = ResearchService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    async def event_generator():
        logger.info(f"Stream started for {session_id}")
        last_heartbeat = time.time()
        heartbeat_interval = 5.0

        try:
            yield {
                "event": "connected",
                "data": json.dumps(
                    {
                        "event_type": "connected",
                        "data": {
                            "session_id": session_id,
                            "timestamp": datetime.datetime.now().isoformat(),
                        },
                    },
                    ensure_ascii=False,
                ),
            }

            while True:
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from {session_id}")
                    break

                current_time = time.time()
                timeout = max(0.1, heartbeat_interval - (current_time - last_heartbeat))

                try:
                    event = await asyncio.wait_for(session.queue.get(), timeout=timeout)

                    if event is None:
                        logger.info(f"Stream ended for {session_id}")
                        break

                    event_type = event.get("event_type", "update")
                    yield {
                        "event": event_type,
                        "data": json.dumps(event, ensure_ascii=False),
                    }
                    last_heartbeat = time.time()

                except TimeoutError:
                    if time.time() - last_heartbeat >= heartbeat_interval:
                        yield {
                            "event": "heartbeat",
                            "data": json.dumps(
                                {
                                    "event_type": "heartbeat",
                                    "data": {"timestamp": datetime.datetime.now().isoformat()},
                                },
                                ensure_ascii=False,
                            ),
                        }
                        last_heartbeat = time.time()

        except Exception as e:
            logger.error(f"Error in stream {session_id}: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "event_type": "error",
                        "data": {"error": str(e)},
                    },
                    ensure_ascii=False,
                ),
            }
        finally:
            logger.info(f"Stream closed for {session_id}")

    return EventSourceResponse(event_generator())


@router.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest, background_tasks: BackgroundTasks) -> MessageResponse:
    """Send a message to an active research session.

    This handles:
    - Clarification answers: When the agent asks questions, send your answer here
    - Steering messages: Guide ongoing research in real-time
    """
    logger.info(f"Message received for session {request.session_id}")

    session = ResearchService.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")

    background_tasks.add_task(ResearchService.continue_research, session, request.message)

    return MessageResponse(
        success=True,
        message="Message received. Research continuing.",
    )


@router.post("/cancel/{session_id}")
async def cancel_research(session_id: str) -> dict:
    """Cancel an active research session."""
    logger.info(f"Cancel requested for {session_id}")

    session = ResearchService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    session.is_active = False
    await session.send_event("research_cancelled", {"message": "Research cancelled by user"})

    return {
        "success": True,
        "message": f"Session {session_id} cancelled",
    }


@router.get("/sessions")
async def list_sessions() -> dict:
    """List all active research sessions."""
    sessions = []
    for session_id, session in ResearchService._sessions.items():
        sessions.append(
            {
                "session_id": session_id,
                "query": session.query,
                "is_active": session.is_active,
            }
        )

    return {
        "sessions": sessions,
        "total": len(sessions),
    }


@router.get("/plan/{session_id}")
async def get_research_plan(session_id: str) -> dict:
    """Get the current research plan (TODO list) for a session."""
    session = ResearchService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not session.todo_manager:
        return {
            "session_id": session_id,
            "plan": "# Research Plan\n\nPlan not yet created. Waiting for research brief...",
            "has_plan": False,
        }

    plan_markdown = session.todo_manager.get_todo_md()

    return {
        "session_id": session_id,
        "plan": plan_markdown,
        "has_plan": True,
    }


@router.get("/status/{session_id}")
async def get_research_status(session_id: str) -> dict:
    """Get detailed status of a research session."""
    session = ResearchService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not session.todo_manager:
        return {
            "session_id": session_id,
            "is_active": session.is_active,
            "has_plan": False,
            "pending_tasks": 0,
            "completed_tasks": 0,
            "research_iterations": 0,
        }

    pending = session.todo_manager.get_pending_tasks()
    completed = session.todo_manager.get_completed_tasks()

    return {
        "session_id": session_id,
        "is_active": session.is_active,
        "has_plan": True,
        "research_topic": session.todo_manager.research_topic,
        "pending_tasks": len(pending),
        "completed_tasks": len(completed),
        "research_iterations": session.todo_manager.research_loop_count,
        "pending_task_list": [
            {
                "id": task.id,
                "description": task.description,
                "priority": task.priority,
                "status": task.status.name,
            }
            for task in pending[:10]
        ],
    }
