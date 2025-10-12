import asyncio
from datetime import datetime
from typing import Annotated, Literal

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool
from langchain_tavily import TavilySearch

from deep_research.config import settings
from deep_research.ml.prompts import SUMMARIZE_WEBPAGE_PROMPT
from deep_research.ml.state import WebSummary
from deep_research.ml.utils import llm


@tool
async def web_search_tool(
    queries: list[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """
    Получает и суммирует результаты веб‑поиска по запросу

    Args:
        queries (list[str]): Поисковые запросы
        max_results (int): Максимальное количество результатов
        topic (Literal["general", "news", "finance"]): Тема поиска

    Returns:
        str: Отформатированный ответ с результатами поиска
    """
    search_tool = TavilySearch(
        tavily_api_key=settings.AGENT.TAVILY_API_KEY,
        max_results=max_results,
        topic=topic,
        include_raw_content=True,
    )
    search_results = await search_tool.abatch(queries)

    unique_search_results = {}
    for response in search_results:
        for result in response["results"]:
            url = result["url"]
            title = result["title"]
            raw_content = result["raw_content"]
            if url not in unique_search_results and raw_content:
                unique_search_results[url] = {
                    "title": title,
                    "raw_content": raw_content,
                }

    summarize_web_tasks = [summarize_web(result["raw_content"]) for result in unique_search_results.values()]
    summaries = await asyncio.gather(*summarize_web_tasks)
    for url, summary in zip(unique_search_results.keys(), summaries, strict=True):
        unique_search_results[url]["summary"] = summary

    formatted_summary = "Результаты поиска:"
    for i, (url, result) in enumerate(unique_search_results.items()):
        formatted_summary += f"\n\nSOURCE {i + 1}: {result['title']}\n"
        formatted_summary += f"URL: {url}\n"
        formatted_summary += f"SUMMARY:\n\n{result['summary']}\n\n"
        formatted_summary += "-" * 100

    return formatted_summary


async def summarize_web(webpage_content: str) -> str:
    """
    Суммирует содержимое веб‑страницы

    Args:
        webpage_content (str): Содержимое веб‑страницы

    Returns:
        str: Форматированный ответ с краткой сводкой и ключевыми фразами
    """
    prompt = SUMMARIZE_WEBPAGE_PROMPT.format(
        webpage_content=webpage_content,
        date=datetime.now().isoformat(),
    )

    structured_llm = llm.with_structured_output(WebSummary)
    response = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    formatted_summary = (
        f"<summary>\n{response.summary}\n</summary>\n\n<key_excerpts>\n{response.key_excerpts}\n</key_excerpts>"
    )
    return formatted_summary


@tool()
def think_tool(reflection: str) -> str:
    """
    Инструмент для стратегической рефлексии по ходу исследования и принятия решений.

    Используйте этот инструмент после каждого поиска для анализа результатов и систематического планирования следующих шагов.
    Это создает осознанную паузу в исследовательском процессе для повышения качества решений.

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
        reflection (str): Ваш подробный анализ хода исследования, находок, пробелов и следующих шагов

    Возвращает:
        str: Подтверждение, что рефлексия зафиксирована для принятия решения
    """
    return f"Рефлексия: {reflection}"


@tool()
def conduct_research_tool(research_topic: str) -> str:
    """
    Инструмент для проведения исследования по заданной теме

    Args:
        research_topic (str): Тема исследования. Должна быть одной темой, и должна быть описана в подробностях (хотя бы абзацем).

    Returns:
        str: Тема исследования.
    """
    return f"Тема исследования: {research_topic}"
