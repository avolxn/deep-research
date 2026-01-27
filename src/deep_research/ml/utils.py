import logging

from langchain_openai import ChatOpenAI

from .config import config

logger = logging.getLogger(__name__)


def get_llm(
    model_name: str = "gpt-oss-120b",
    temperature: float = 0.7,
    max_tokens: int = None,
) -> ChatOpenAI:
    """Factory function for creating LLM instance.

    Models are configured through environment variables in config.

    Args:
        model_name: Name of the model to use
        temperature: Temperature for generation
        max_tokens: Maximum tokens for generation

    Returns:
        Configured ChatOpenAI instance

    Raises:
        ValueError: If provider is not configured
    """
    if not config.YANDEX_GPT_API_KEY or not config.YANDEX_GPT_FOLDER_ID:
        raise ValueError(".env not configured: need YANDEX_GPT_API_KEY and YANDEX_GPT_FOLDER_ID")

    return ChatOpenAI(
        api_key=config.YANDEX_GPT_API_KEY,
        base_url="https://llm.api.cloud.yandex.net/v1",
        model=f"gpt://{config.YANDEX_GPT_FOLDER_ID}/{model_name}",
        temperature=temperature,
        max_tokens=max_tokens,
        default_headers={"x-folder-id": config.YANDEX_GPT_FOLDER_ID},
    )
