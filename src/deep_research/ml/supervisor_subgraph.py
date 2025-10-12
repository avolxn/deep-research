import asyncio
from datetime import datetime
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, filter_messages
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from deep_research.ml.prompts import SUPERVISOR_PROMPT
from deep_research.ml.researcher_subgraph import researcher_subgraph
from deep_research.ml.state import SupervisorState
from deep_research.ml.tools import conduct_research_tool, think_tool
from deep_research.ml.utils import llm


async def supervisor(state: SupervisorState) -> SupervisorState:
    """Супервизор, который выполняет инструменты супервизора"""
    supervisor_messages = state["messages"]

    prompt = SUPERVISOR_PROMPT.format(date=datetime.now().isoformat())
    messages_with_system = [SystemMessage(content=prompt)] + supervisor_messages

    llm_with_tools = llm.bind_tools([think_tool, conduct_research_tool])
    response = await llm_with_tools.ainvoke(messages_with_system)

    return {"messages": [response]}


async def supervisor_tools(state: SupervisorState) -> Command[Literal["supervisor", "__end__"]]:
    """Выполняет инструменты супервизора"""
    supervisor_messages = state["messages"]
    last_message = supervisor_messages[-1]
    tool_calls = last_message.tool_calls

    if not tool_calls:
        notes = [tool_message.content for tool_message in filter_messages(supervisor_messages, include_types="tool")]
        return Command(
            goto=END,
            update={"notes": notes},
        )

    tool_messages = []
    all_raw_notes = []

    think_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "think_tool"]
    for tool_call in think_calls:
        reflection = await think_tool.ainvoke(tool_call["args"])

        tool_messages.append(
            ToolMessage(
                content=reflection,
                name="think_tool",
                tool_call_id=tool_call["id"],
            )
        )

    conduct_research_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "conduct_research_tool"]
    conduct_research_tasks = [
        researcher_subgraph.ainvoke(
            {"researcher_messages": [HumanMessage(content=tool_call["args"]["research_topic"])]}
        )
        for tool_call in conduct_research_calls
    ]
    responses = await asyncio.gather(*conduct_research_tasks)
    for response, tool_call in zip(responses, conduct_research_calls, strict=True):
        compressed_research = response["compressed_research"]
        raw_notes = response["raw_notes"]
        all_raw_notes.extend(raw_notes)

        tool_messages.append(
            ToolMessage(
                content=compressed_research,
                name="conduct_research_tool",
                tool_call_id=tool_call["id"],
            )
        )

    return Command(
        goto="supervisor",
        update={
            "messages": tool_messages,
            "raw_notes": all_raw_notes,
        },
    )


workflow = StateGraph(SupervisorState)

workflow.add_node("supervisor", supervisor)
workflow.add_node("supervisor_tools", supervisor_tools)

workflow.add_edge(START, "supervisor")
workflow.add_edge("supervisor", "supervisor_tools")

supervisor_subgraph = workflow.compile()
