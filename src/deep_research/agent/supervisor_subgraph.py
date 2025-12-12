import asyncio
from datetime import datetime
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, filter_messages
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from deep_research.agent.config import config
from deep_research.agent.prompts import SUPERVISOR_PROMPT
from deep_research.agent.researcher_subgraph import researcher_subgraph
from deep_research.agent.state import SupervisorState
from deep_research.agent.tools import conduct_research_tool, research_complete_tool, think_tool
from deep_research.agent.utils import get_llm

SUPERVISOR_TOOLS = [think_tool, conduct_research_tool, research_complete_tool]


async def supervisor(state: SupervisorState) -> Command[Literal["supervisor_tools"]]:
    """Ведущий супервизор исследования, который планирует стратегию и делегирует задачи исследователям."""
    supervisor_messages = state.get("supervisor_messages", [])

    system_prompt = SUPERVISOR_PROMPT.format(
        date=datetime.now().strftime("%c"),
        max_concurrent_research_units=config.MAX_CONCURRENT_RESEARCH_UNITS,
        max_researcher_iterations=config.MAX_RESEARCHER_ITERATIONS,
    )
    supervisor_messages = [SystemMessage(content=system_prompt)] + supervisor_messages

    llm = get_llm(**config.research_model.model_dump())
    llm_with_tools = llm.bind_tools(SUPERVISOR_TOOLS)
    response = await llm_with_tools.ainvoke(supervisor_messages)

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1,
        },
    )


async def supervisor_tools(state: SupervisorState) -> Command[Literal["supervisor", "__end__"]]:
    """Выполняет инструменты, вызванные супервизором, включая делегирование исследования и стратегическое мышление."""
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    last_message = supervisor_messages[-1]
    tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else []

    exceeded_iterations = research_iterations > config.MAX_RESEARCHER_ITERATIONS
    no_tool_calls = not tool_calls
    research_complete_called = any(tool_call["name"] == "research_complete_tool" for tool_call in tool_calls)
    if exceeded_iterations or no_tool_calls or research_complete_called:
        notes = [tool_message.content for tool_message in filter_messages(supervisor_messages, include_types="tool")]
        return Command(
            goto=END,
            update={
                "notes": notes,
                "research_task": state.get("research_task", ""),
            },
        )

    all_tool_messages = []
    all_raw_notes = []

    think_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "think_tool"]
    for tool_call in think_calls:
        tool_message = think_tool.invoke(tool_call)
        all_tool_messages.append(tool_message)

    conduct_research_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "conduct_research_tool"]
    if conduct_research_calls:
        allowed_conduct_research_calls = conduct_research_calls[: config.MAX_CONCURRENT_RESEARCH_UNITS]
        overflow_conduct_research_calls = conduct_research_calls[config.MAX_CONCURRENT_RESEARCH_UNITS :]
        research_tasks = [
            researcher_subgraph.ainvoke(
                {
                    "researcher_messages": [HumanMessage(content=tool_call["args"]["research_topic"])],
                    "research_topic": tool_call["args"]["research_topic"],
                }
            )
            for tool_call in allowed_conduct_research_calls
        ]
        responses = await asyncio.gather(*research_tasks)

        for response, tool_call in zip(responses, allowed_conduct_research_calls, strict=True):
            content = response.get("compressed_research", "Ошибка при синтезе исследовательского отчёта")
            raw_notes = response.get("raw_notes", [])
            all_raw_notes.extend(raw_notes)

            all_tool_messages.append(
                ToolMessage(
                    content=content,
                    name="conduct_research_tool",
                    tool_call_id=tool_call["id"],
                )
            )

        for tool_call in overflow_conduct_research_calls:
            all_tool_messages.append(
                ToolMessage(
                    content=f"Ошибка: Это исследование не было выполнено, так как превышено максимальное количество параллельных исследовательских единиц. Попробуйте снова с {config.MAX_CONCURRENT_RESEARCH_UNITS} или меньше единицами.",
                    name="conduct_research_tool",
                    tool_call_id=tool_call["id"],
                )
            )

    research_complete_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "research_complete_tool"]
    for tool_call in research_complete_calls:
        tool_message = research_complete_tool.invoke(tool_call)
        all_tool_messages.append(tool_message)

    update_payload = {
        "supervisor_messages": all_tool_messages,
        "raw_notes": all_raw_notes,
    }

    return Command(
        goto="supervisor",
        update=update_payload,
    )


workflow = StateGraph(SupervisorState)

workflow.add_node("supervisor", supervisor)
workflow.add_node("supervisor_tools", supervisor_tools)

workflow.add_edge(START, "supervisor")
workflow.add_edge("supervisor", "supervisor_tools")

supervisor_subgraph = workflow.compile()
