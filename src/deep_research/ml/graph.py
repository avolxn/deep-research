from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from deep_research.ml.prompts import (
    CLARIFY_WITH_USER_PROMPT,
    GENERATE_REPORT_PROMPT,
    WRITE_RESEARCH_BRIEF_PROMPT,
)
from deep_research.ml.state import ClarifyWithUser, DeepResearchState
from deep_research.ml.supervisor_subgraph import supervisor_subgraph
from deep_research.ml.utils import llm


async def clarify_with_user(state: DeepResearchState) -> Command[Literal["write_research_brief", "__end__"]]:
    """Уточняет у пользователя информацию, если она неполная или некорректная"""
    messages = state["messages"]

    prompt = CLARIFY_WITH_USER_PROMPT.format(
        messages=get_buffer_string(messages),
        date=datetime.now().isoformat(),
    )

    structured_llm = llm.with_structured_output(ClarifyWithUser)
    response = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    if response.need_clarification:
        questions = response.questions
        return Command(
            goto=END,
            update={"messages": [AIMessage(content=questions)]},
        )
    else:
        verification = response.verification
        return Command(
            goto="write_research_brief",
            update={"messages": [AIMessage(content=verification)]},
        )


async def write_research_brief(state: DeepResearchState) -> DeepResearchState:
    """Преобразует диалог в одно точно и детализированное исследовательское задание"""
    messages = state["messages"]

    prompt = WRITE_RESEARCH_BRIEF_PROMPT.format(
        messages=get_buffer_string(messages),
        date=datetime.now().isoformat(),
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    research_brief = response.content

    return {
        "messages": [HumanMessage(content=research_brief)],
        "research_brief": research_brief,
    }


async def generate_report(state: DeepResearchState) -> DeepResearchState:
    """Генерирует отчет на основе исследовательского задания и информации, полученной от исследователей"""
    messages = state["messages"]
    research_brief = state["research_brief"]
    notes = state["notes"]
    information = "\n".join(notes)

    prompt = GENERATE_REPORT_PROMPT.format(
        research_brief=research_brief,
        messages=get_buffer_string(messages),
        information=information,
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    final_report = response.content

    return {
        "messages": [AIMessage(content=final_report)],
        "final_report": final_report,
    }


workflow = StateGraph(DeepResearchState)

workflow.add_node("clarify_with_user", clarify_with_user)
workflow.add_node("write_research_brief", write_research_brief)
workflow.add_node("supervisor", supervisor_subgraph)
workflow.add_node("generate_report", generate_report)

workflow.add_edge(START, "clarify_with_user")
workflow.add_edge("write_research_brief", "supervisor")
workflow.add_edge("supervisor", "generate_report")
workflow.add_edge("generate_report", END)

deep_research_agent = workflow.compile(checkpointer=MemorySaver())
