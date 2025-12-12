import logging

from langchain_openai import ChatOpenAI

from .config import config

logger = logging.getLogger(__name__)


def get_llm(
    model_name: str = "gpt-oss-120b",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> ChatOpenAI:
    """
    Factory функция для создания экземпляра LLM.

    Модели настраиваются через переменные окружения в config.

    Args:
        model_name: Полное название модели
        temperature: Температура генерации (0.0-2.0)
        max_tokens: Максимальное количество токенов

    Returns:
        Экземпляр LLM (ChatOpenAI)

    Raises:
        ValueError: Если провайдер не поддерживается или не настроен
    """
    if not config.YANDEX_GPT_API_KEY or not config.YANDEX_GPT_FOLDER_ID:
        raise ValueError(".env не настроен: нужны YANDEX_GPT_API_KEY и YANDEX_GPT_FOLDER_ID")

    return ChatOpenAI(
        api_key=config.YANDEX_GPT_API_KEY,
        base_url="https://llm.api.cloud.yandex.net/v1",
        model=f"gpt://{config.YANDEX_GPT_FOLDER_ID}/{model_name}",
        temperature=temperature,
        max_tokens=max_tokens,
        default_headers={"x-folder-id": config.YANDEX_GPT_FOLDER_ID},
    )
