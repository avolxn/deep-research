from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from deep_research.agent.config import config
from deep_research.agent.prompts import (
    CLARIFY_WITH_USER_PROMPT,
    GENERATE_REPORT_PROMPT,
    WRITE_RESEARCH_TASK_PROMPT,
)
from deep_research.agent.state import ClarifyWithUser, DeepResearchState, ResearchQuestion
from deep_research.agent.supervisor_subgraph import supervisor_subgraph
from deep_research.agent.utils import get_llm


async def clarify_with_user(state: DeepResearchState) -> Command[Literal["write_research_task", "__end__"]]:
    """Анализирует сообщения пользователя и задаёт уточняющие вопросы, если область исследования неясна."""
    messages = state["messages"]

    prompt = CLARIFY_WITH_USER_PROMPT.format(
        messages=get_buffer_string(messages),
        date=datetime.now().strftime("%c"),
    )

    llm = get_llm(**config.research_model.model_dump())
    structured_llm = llm.with_structured_output(ClarifyWithUser)
    response = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    if response.need_clarification:
        return Command(
            goto=END,
            update={"messages": [AIMessage(content=response.questions)]},
        )
    else:
        return Command(
            goto="write_research_task",
            update={"messages": [AIMessage(content=response.verification)]},
        )


async def write_research_task(state: DeepResearchState) -> Command[Literal["research_supervisor"]]:
    """Преобразует сообщения пользователя в структурированное исследовательское задание и инициализирует супервизора.

    Эта функция анализирует сообщения пользователя и генерирует детальное исследовательское задание,
    которое будет направлять супервизора исследования.
    """
    messages = state["messages"]

    prompt = WRITE_RESEARCH_TASK_PROMPT.format(
        messages=get_buffer_string(messages),
        date=datetime.now().strftime("%c"),
    )

    llm = get_llm(**config.research_model.model_dump())
    structured_llm = llm.with_structured_output(ResearchQuestion)
    response = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    return Command(
        goto="research_supervisor",
        update={
            "research_task": response.research_task,
            "supervisor_messages": [HumanMessage(content=response.research_task)],
        },
    )


async def generate_report(state: DeepResearchState) -> DeepResearchState:
    """Генерирует финальный исчерпывающий исследовательский отчёт."""
    messages = state["messages"]
    research_task = state.get("research_task", "")
    notes = state.get("notes", [])
    findings = "\n".join(notes)

    prompt = GENERATE_REPORT_PROMPT.format(
        research_task=research_task,
        messages=get_buffer_string(messages),
        findings=findings,
        date=datetime.now().strftime("%c"),
    )

    llm = get_llm(**config.report_model.model_dump())
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    final_report = response.content

    return {
        "messages": [AIMessage(content=final_report)],
        "final_report": final_report,
    }


workflow = StateGraph(DeepResearchState)

workflow.add_node("clarify_with_user", clarify_with_user)
workflow.add_node("write_research_task", write_research_task)
workflow.add_node("research_supervisor", supervisor_subgraph)
workflow.add_node("generate_report", generate_report)

workflow.add_edge(START, "clarify_with_user")
workflow.add_edge("research_supervisor", "generate_report")
workflow.add_edge("generate_report", END)

deep_research_agent = workflow.compile(checkpointer=MemorySaver())
