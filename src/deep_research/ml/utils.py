from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI

from deep_research.config import settings

model_exception_message = """Ошибка при инициализации языковой модели (LLM):
Убедитесь, что указан верный API ключ в .env файле.
Gemini модель из Google AI Studio не поддерживается на территории Российской Федерации.
Для корректной работы модели необходимо использовать VPN.
Не все VPN сервисы работают корректно: бывают случаи некорректного обхода блокировок или длительных задержек при вызове модели.
Стабильно работает бесплатный VPN Proxy Master (доступен в AppStore). Может потребоваться множественное переподключение VPN."""


def get_llm() -> ChatGoogleGenerativeAI:
    """Получить Gemini модель из Google AI Studio

    Raises:
        Exception: Ошибка при инициализации языковой модели (из-за неверного API или невключенного/неподходящего VPN)

    Returns:
        ChatGoogleGenerativeAI: Gemini модель из Google AI Studio
    """
    rate_limiter = InMemoryRateLimiter(
        requests_per_second=settings.AGENT.RATE_LIMIT_PER_MINUTE / 60,
        check_every_n_seconds=1,
        max_bucket_size=1,
    )

    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.AGENT.LLM_NAME,
            google_api_key=settings.AGENT.GOOGLE_API_KEY,
            rate_limiter=rate_limiter,
        )

        # _ = llm.invoke("Hello!")

        return llm
    except Exception:
        raise Exception(model_exception_message) from None


# Синглтон
llm = get_llm()
