import asyncio
from typing import Annotated, Literal

from langchain_core.tools import InjectedToolArg, tool
from tavily import AsyncTavilyClient

from deep_research.ml.config import config

LLM_SEMAPHORE = asyncio.Semaphore(3)


@tool()
async def web_search_tool(
    queries: list[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """Получает и суммирует результаты веб-поиска через Tavily.

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
    """Удаляет дубликаты в результатах поиска по URL."""
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
    """Суммирует содержимое веб-страницы с использованием AI-модели."""
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
    """Инструмент для стратегической рефлексии по ходу исследования и принятия решений."""
    return f"Рефлексия зафиксирована: {reflection}"


@tool
def conduct_research_tool(research_topic: str) -> str:
    """Инструмент для делегирования исследования специализированному под-агенту."""
    return f"Тема исследования делегирована: {research_topic}"


@tool
def research_complete_tool() -> str:
    """Инструмент для указания на завершение исследования."""
    return "Исследование завершено."
