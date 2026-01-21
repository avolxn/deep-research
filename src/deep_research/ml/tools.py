import asyncio
import logging
from datetime import datetime
from typing import Annotated, Literal

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool
from pydantic import BaseModel, Field
from tavily import AsyncTavilyClient

from deep_research.ml.config import config
from deep_research.ml.prompts import SUMMARIZE_WEBPAGE_PROMPT
from deep_research.ml.utils import get_llm

logger = logging.getLogger(__name__)

LLM_SEMAPHORE = asyncio.Semaphore(3)


class WebSummary(BaseModel):
    """Research summary with key findings."""

    summary: str = Field(
        description="Brief summary (paragraphs and/or bullet points)",
    )
    key_excerpts: str = Field(
        description="Quote 1, quote 2, quote 3 ... maximum 5 quotes",
    )


@tool()
async def web_search_tool(
    queries: list[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """Fetch and summarize search results from Tavily search API.

    Args:
        queries: List of search queries to execute
        max_results: Maximum number of results to return per query
        topic: Topic filter for search results (general, news, or finance)

    Returns:
        Formatted string containing summarized search results
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
        return "No search results found. Try different search queries."

    formatted_summary = "Search results:\n\n"
    for i, (url, result) in enumerate(unique_search_results.items()):
        formatted_summary += f"\n--- SOURCE {i + 1}: {result['title']} ---\n"
        formatted_summary += f"URL: {url}\n\n"
        formatted_summary += f"CONTENT:\n{result['summary']}\n\n"
        formatted_summary += "-" * 80 + "\n"

    return formatted_summary


def deduplicate_search_results(search_results: list[list[dict]]) -> dict[str, dict]:
    """Removes duplicates in search results by URL.

    Args:
        search_results: List of search result lists from multiple queries

    Returns:
        Dictionary mapping URLs to deduplicated search results
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
    """Summarizes webpage content using an AI model.

    Args:
        webpage_content: Raw webpage content to summarize

    Returns:
        Summarized content as string
    """
    async with LLM_SEMAPHORE:
        try:
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
        except Exception as e:
            error_msg = str(e)
            if "ContentFilterFinishReasonError" in error_msg or "content filter" in error_msg.lower():
                logger.warning(f"Content filter rejected webpage content: {error_msg}")
                return "<summary>Content was rejected by content filter and could not be summarized.</summary>"
            else:
                logger.error(f"Error summarizing webpage: {error_msg}")
                return f"<summary>Error summarizing content: {error_msg[:100]}</summary>"


@tool()
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


@tool
def research_complete_tool() -> str:
    """Tool to indicate research completion.

    Returns:
        Completion message string
    """
    return "Research complete."
