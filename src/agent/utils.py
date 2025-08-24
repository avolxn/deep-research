import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.config import GOOGLE_API_KEY, LLM_NAME

model_exception_message = """Ошибка при инициализации языковой модели (LLM):
Убедитесь, что указан верный API ключ в .env файле.
Gemini модель из Google AI Studio не поддерживается на территории Российской Федерации.
Для корректной работы модели необходимо использовать VPN.
Не все VPN сервисы работают корректно: бывают случаи некорректного обхода блокировок или длительных задержек при вызове модели.
Стабильно работает бесплатный VPN Proxy Master (доступен в AppStore). Может потребоваться множественное переподключение VPN."""


class LLM:
    """Обертка над моделью для вызова с повторением при превышении квоты/лимита запросов."""

    def __init__(self) -> None:
        """
        Получить Gemini модель из Google AI Studio

        Raises:
            RuntimeError: Ошибка при инициализации языковой модели (из-за неверного API или невключенного/неподходящего VPN)
        """
        try:
            llm = ChatGoogleGenerativeAI(
                model=LLM_NAME,
                google_api_key=GOOGLE_API_KEY,
            )

            _ = llm.invoke("Hello!")

            self.llm = llm

        except Exception:
            raise RuntimeError(model_exception_message) from None

    async def _arun_with_retry(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        for _ in range(3):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_text = str(e)
                is_quota = "429" in error_text or "ResourceExhausted" in error_text or "quota" in error_text.lower()
                if not is_quota:
                    raise

                await asyncio.sleep(60)

    def _wrap_runnable(self, runnable: Any) -> Any:
        """Обёртка runnable: синхронные и асинхронные вызовы через ретраи."""

        async def ainvoke(*args: Any, **kwargs: Any) -> Any:
            return await self._arun_with_retry(runnable.ainvoke, *args, **kwargs)

        async def astream(*args: Any, **kwargs: Any) -> Any:
            return await self._arun_with_retry(runnable.astream, *args, **kwargs)

        return SimpleNamespace(
            ainvoke=ainvoke,
            astream=astream,
        )

    def bind_tools(self, *args: Any, **kwargs: Any) -> Any:
        return self._wrap_runnable(self.llm.bind_tools(*args, **kwargs))

    def with_structured_output(self, *args: Any, **kwargs: Any) -> Any:
        return self._wrap_runnable(self.llm.with_structured_output(*args, **kwargs))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self._arun_with_retry(self.llm.ainvoke, *args, **kwargs)

    async def astream(self, *args: Any, **kwargs: Any) -> Any:
        return await self._arun_with_retry(self.llm.astream, *args, **kwargs)


# Синглтоны
llm = LLM()
