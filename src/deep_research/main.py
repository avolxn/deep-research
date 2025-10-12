import uvicorn

from deep_research.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "deep_research.backend.app:app",
        host=settings.API.HOST,
        port=settings.API.PORT,
        reload=settings.API.RELOAD,
    )
