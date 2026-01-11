"""FastAPI application for Deep Research."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from deep_research.api.router import router as research_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для приложения."""
    logger.info("🚀 Deep Research API запускается...")
    yield
    logger.info("👋 Deep Research API завершает работу...")


app = FastAPI(
    title="Deep Research API",
    description="API для глубокого исследования тем с использованием LLM и веб-поиска",
    version=VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Необработанная ошибка: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера", "error": str(exc)},
    )


# Подключение роутеров
app.include_router(research_router)


@app.get("/", tags=["Root"])
async def root():
    """Корневой endpoint с информацией об API."""
    return {
        "service": "Deep Research API",
        "version": VERSION,
        "status": "running",
        "endpoints": {
            "POST /api/research": "Запустить исследование",
            "GET /api/research/stream/{thread_id}": "Поток событий исследования",
            "GET /api/research/status/{thread_id}": "Статус исследования",
            "POST /api/research/stop/{thread_id}": "Остановить исследование",
            "GET /api/research/health": "Проверка здоровья API",
        },
        "docs": "/docs",
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
