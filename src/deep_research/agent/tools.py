import asyncio
from datetime import datetime
from typing import Annotated, Literal

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool
from tavily import AsyncTavilyClient

from deep_research.agent.config import config
from deep_research.agent.prompts import SUMMARIZE_WEBPAGE_PROMPT
from deep_research.agent.state import WebSummary
from deep_research.agent.utils import get_llm

LLM_SEMAPHORE = asyncio.Semaphore(3)


@tool()
async def web_search_tool(
    queries: list[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """Получает и суммирует результаты веб-поиска через

    Args:
        queries: Список поисковых запросов для выполнения
        max_results: Максимальное количество результатов на запрос
        topic: Фильтр темы для результатов поиска (general, news или finance)

    Returns:
        Форматированная строка с суммаризированными результатами поиска
    """
    client = AsyncTavilyClient(api_key=config.TAVILY_API_KEY)
    search_tasks = [
        client.search(
            query=query,
            max_results=max_results,
            topic=topic,
            include_raw_content=True,
        )
        for query in queries
    ]
    responses = await asyncio.gather(*search_tasks)
    search_results = [response.get("results", []) for response in responses]

    unique_search_results = deduplicate_search_results(search_results)

    summarize_web_tasks = [summarize_web(result["raw_content"]) for result in unique_search_results.values()]
    summaries = await asyncio.gather(*summarize_web_tasks)
    for url, summary in zip(unique_search_results.keys(), summaries, strict=True):
        unique_search_results[url]["summary"] = summary

    if not unique_search_results:
        return "Результаты поиска не найдены. Попробуйте другие поисковые запросы."

    formatted_summary = "Результаты поиска:\n\n"
    for i, (url, result) in enumerate(unique_search_results.items()):
        formatted_summary += f"\n--- ИСТОЧНИК {i + 1}: {result['title']} ---\n"
        formatted_summary += f"URL: {url}\n\n"
        formatted_summary += f"СОДЕРЖАНИЕ:\n{result['summary']}\n\n"
        formatted_summary += "-" * 80 + "\n"

    return formatted_summary


def deduplicate_search_results(search_results: list[list[dict]]) -> dict[str, dict]:
    """Удаляет дубликаты в результатах поиска по URL.

    Args:
        search_results: Список результатов поиска (каждый элемент — список результатов от одного запроса)

    Returns:
        Словарь уникальных результатов поиска с URL в качестве ключа
    """
    unique_search_results = {}
    for results in search_results:
        for result in results:
            url = result.get("url")
            title = result.get("title")
            raw_content = result.get("raw_content")
            if url and url not in unique_search_results and raw_content:
                unique_search_results[url] = {
                    "title": title,
                    "raw_content": raw_content,
                }

    return unique_search_results


async def summarize_web(webpage_content: str) -> str:
    """Суммирует содержимое веб-страницы с использованием AI-модели.

    Args:
        webpage_content: Сырое содержимое веб-страницы для суммаризации

    Returns:
        Форматированное резюме с ключевыми выдержками
    """
    async with LLM_SEMAPHORE:
        prompt = SUMMARIZE_WEBPAGE_PROMPT.format(
            webpage_content=webpage_content,
            date=datetime.now().strftime("%c"),
        )

        summarization_llm = get_llm(**config.summarization_model.model_dump())
        summarization_model = summarization_llm.with_structured_output(WebSummary)

        response = await summarization_model.ainvoke([HumanMessage(content=prompt)])

        formatted_summary = (
            f"<summary>\n{response.summary}\n</summary>\n\n<key_excerpts>\n{response.key_excerpts}\n</key_excerpts>"
        )
        return formatted_summary


@tool
def think_tool(reflection: str) -> str:
    """Инструмент для стратегической рефлексии по ходу исследования и принятия решений.

    Используйте этот инструмент после каждого поиска для систематического анализа результатов
    и планирования следующих шагов. Это создаёт осознанную паузу в исследовательском процессе
    для повышения качества решений.

    Когда использовать:
    - После получения результатов поиска: Какую ключевую информацию я нашёл?
    - Перед выбором следующих шагов: Достаточно ли у меня данных для полного ответа?
    - При оценке пробелов: Какой конкретной информации мне ещё не хватает?
    - Перед завершением исследования: Могу ли я сейчас дать полный ответ?

    Рефлексия должна включать:
    1. Анализ текущих находок — какую конкретную информацию я собрал?
    2. Оценку пробелов — какой важной информации всё ещё не хватает?
    3. Оценку качества — достаточно ли у меня доказательств/примеров для хорошего ответа?
    4. Стратегическое решение — стоит ли продолжать поиск или уже можно отвечать?

    Args:
        reflection: Подробный анализ хода исследования, находок, пробелов и следующих шагов

    Returns:
        Подтверждение, что рефлексия зафиксирована для принятия решения
    """
    return f"Рефлексия зафиксирована: {reflection}"


@tool
def conduct_research_tool(research_topic: str) -> str:
    """Инструмент для делегирования исследования специализированному под-агенту.

    Используется руководителем исследования для делегирования конкретных исследовательских
    задач под-агентам. Каждый вызов создаёт выделенного исследовательского агента для
    указанной темы.

    Важные правила:
    - Тема должна быть самодостаточной — под-агенты не видят контекст других агентов
    - Избегайте аббревиатур и сокращений — формулируйте явно и ясно
    - Тема должна быть описана подробно (минимум абзац)
    - Каждый вызов — это отдельная, независимая исследовательская задача

    Args:
        research_topic: Тема исследования. Должна быть одной конкретной темой,
                       описанной подробно и самодостаточно.

    Returns:
        Подтверждение темы исследования для делегирования
    """
    return f"Тема исследования делегирована: {research_topic}"


@tool
def research_complete_tool() -> str:
    """Инструмент для указания на завершение исследования.

    Вызывается руководителем исследования или исследователем, когда собрано достаточно информации
    для ответа на исследовательский вопрос. После вызова этого инструмента
    исследовательская фаза завершается.

    Для супервизора: после вызова начинается генерация финального отчёта.
    Для исследователя: после вызова результаты передаются супервизору.

    Когда использовать:
    - Когда можно уверенно ответить на вопрос пользователя
    - Когда собрано достаточно релевантных источников и примеров
    - Когда дополнительные поиски вряд ли добавят существенную информацию

    Returns:
        Подтверждение завершения исследования
    """
    return "Исследование завершено."
