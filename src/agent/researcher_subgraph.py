from datetime import datetime

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.prompts import COMPRESS_RESEARCH_SYSTEM_PROMPT, RESEARCH_SYSTEM_PROMPT
from agent.state import ResearcherState
from agent.tools import think_tool, web_search_tool
from agent.utils import llm


async def researcher(state: ResearcherState) -> ResearcherState:
    """Исследовательский агент, который проводит исследование по заданной теме"""
    researcher_messages = state["researcher_messages"]

    prompt = RESEARCH_SYSTEM_PROMPT.format(date=datetime.now().isoformat())
    messages_with_system = [SystemMessage(content=prompt)] + researcher_messages

    llm_with_tools = llm.bind_tools([web_search_tool, think_tool])
    response = await llm_with_tools.ainvoke(messages_with_system)

    return {"researcher_messages": [response]}


async def compress_research(state: ResearcherState) -> ResearcherState:
    """Сжимает исследование, чтобы уменьшить количество информации, которую нужно обработать"""
    researcher_messages = state["researcher_messages"]

    prompt = COMPRESS_RESEARCH_SYSTEM_PROMPT.format(date=datetime.now().isoformat())
    messages_with_system = [SystemMessage(content=prompt)] + researcher_messages

    response = await llm.ainvoke(messages_with_system)
    compressed_research = response.content

    raw_notes = [message.content for message in researcher_messages]

    return {
        "raw_notes": raw_notes,
        "compressed_research": compressed_research,
    }


async def custom_condition(state: ResearcherState):
    return tools_condition(state, messages_key="researcher_messages")


workflow = StateGraph(ResearcherState)

workflow.add_node("researcher", researcher)
workflow.add_node("researcher_tools", ToolNode([web_search_tool, think_tool], messages_key="researcher_messages"))
workflow.add_node("compress_research", compress_research)

workflow.add_edge(START, "researcher")
workflow.add_conditional_edges(
    "researcher",
    custom_condition,
    {
        "tools": "researcher_tools",
        "__end__": "compress_research",
    },
)
workflow.add_edge("researcher_tools", "researcher")
workflow.add_edge("compress_research", END)

researcher_subgraph = workflow.compile()
