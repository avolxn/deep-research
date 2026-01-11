from datetime import datetime
from typing import Literal

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.types import Command

from deep_research.ml.config import config
from deep_research.ml.prompts import (
    RESEARCH_SYSTEM_PROMPT,
)
from deep_research.ml.state import ResearcherState
from deep_research.ml.tools import research_complete_tool, think_tool, web_search_tool
from deep_research.ml.utils import get_llm

RESEARCHER_TOOLS = [web_search_tool, think_tool, research_complete_tool]


async def researcher(state: ResearcherState) -> Command[Literal["researcher_tools"]]:
    """Исследователь, проводящий сфокусированное исследование по конкретным темам."""
    researcher_messages = state.get("researcher_messages", [])

    system_prompt = RESEARCH_SYSTEM_PROMPT.format(date=datetime.now().strftime("%c"))
    messages = [SystemMessage(content=system_prompt)] + researcher_messages

    llm = get_llm(**config.research_model.model_dump())
    llm_with_tools = llm.bind_tools(RESEARCHER_TOOLS)
    response = await llm_with_tools.ainvoke(messages)

    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


async def researcher_tools(state: ResearcherState) -> Command[Literal["researcher", "compress_research"]]:
    """Выполняет инструменты исследователя с проверкой лимита итераций."""
    researcher_messages = state.get("researcher_messages", [])
    tool_call_iterations = state.get("tool_call_iterations", 0)
    last_message = researcher_messages[-1]
    tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else []

    exceeded_iterations = tool_call_iterations >= config.MAX_TOOL_CALL_ITERATIONS
    no_tool_calls = not tool_calls
    research_complete_called = any(tool_call["name"] == "research_complete_tool" for tool_call in tool_calls)
    if exceeded_iterations or no_tool_calls or research_complete_called:
        return Command(goto="compress_research")

    all_tool_messages = []

    think_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "think_tool"]
    for tool_call in think_calls:
        tool_message = think_tool.invoke(tool_call)
        all_tool_messages.append(tool_message)

    web_search_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "web_search_tool"]
    for tool_call in web_search_calls:
        try:
            result = await web_search_tool.ainvoke(tool_call["args"])
            content = result if isinstance(result, str) else str(result)
        except Exception as e:
            content = f"Ошибка при выполнении поиска: {e}"

        all_tool_messages.append(
            ToolMessage(
                content=content,
                name="web_search_tool",
                tool_call_id=tool_call["id"],
            )
        )

    return Command(
        goto="researcher",
        update={"researcher_messages": all_tool_messages},
    )


async def compress_research(state: ResearcherState) -> ResearcherOutputState:
    """Сжимает и синтезирует результаты исследования в краткое, структурированное резюме."""
    researcher_messages = state.get("researcher_messages", [])

    system_prompt = COMPRESS_RESEARCH_SYSTEM_PROMPT.format(date=datetime.now().strftime("%c"))
    researcher_messages_with_instruction = researcher_messages + [HumanMessage(content=COMPRESS_RESEARCH_HUMAN_MESSAGE)]
    messages = [SystemMessage(content=system_prompt)] + researcher_messages_with_instruction

    llm = get_llm(**config.compression_model.model_dump())
    response = await llm.ainvoke(messages)
    compressed_research = response.content

    raw_notes = [message.content for message in researcher_messages if hasattr(message, "content")]

    return {
        "compressed_research": compressed_research,
        "raw_notes": raw_notes,
    }


workflow = StateGraph(ResearcherState, output=ResearcherOutputState)

workflow.add_node("researcher", researcher)
workflow.add_node("researcher_tools", researcher_tools)
workflow.add_node("compress_research", compress_research)

workflow.add_edge(START, "researcher")
workflow.add_edge("compress_research", END)

researcher_subgraph = workflow.compile()
