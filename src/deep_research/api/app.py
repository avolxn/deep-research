"""FastAPI application for Deep Research API."""

import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deep_research.api.router import router

load_dotenv()

if os.getenv("LANGSMITH_TRACING") == "true":
    logging.info("LangSmith tracing enabled for project: %s", os.getenv("LANGSMITH_PROJECT"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backend_logs.txt"),
        logging.StreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.INFO)
logging.getLogger("langgraph").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Deep Research API",
    description="An API for performing deep research on topics using LLMs and web search",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint that returns basic API information.

    Returns:
        Dictionary with API message, endpoints list, and documentation link
    """
    return {
        "message": "Deep Research API is running",
        "endpoints": {
            "POST /research": "Start a new research session",
            "GET /stream/{session_id}": "Stream research updates via SSE",
            "POST /message": "Send message to session (clarification/steering)",
            "POST /cancel/{session_id}": "Cancel an active research session",
            "GET /sessions": "List all active sessions",
            "GET /plan/{session_id}": "Get current research plan (TODO list)",
            "GET /status/{session_id}": "Get research status and progress",
        },
        "documentation": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "deep_research.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
