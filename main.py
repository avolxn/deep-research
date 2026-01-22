"""Main entry point for Deep Research API."""

import uvicorn

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "deep_research.api.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
