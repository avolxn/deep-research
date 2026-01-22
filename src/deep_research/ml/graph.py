"""
Main Deep Research graph with task-driven planning.
All nodes are at the same level for better streaming support.
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from deep_research.ml.config import config
from deep_research.ml.prompts import (
    CLARIFY_WITH_USER_PROMPT,
    GENERATE_REPORT_PROMPT,
    REFLECT_ON_TASKS_PROMPT,
    WRITE_RESEARCH_BRIEF_PROMPT,
)
from deep_research.ml.researcher_subgraph import researcher_subgraph
from deep_research.ml.state import DeepResearchState
from deep_research.ml.todo_manager import ResearchTodoManager, TaskStatus
from deep_research.ml.utils import get_llm

logger = logging.getLogger(__name__)


class ResearchQuestion(BaseModel):
    """Research question and brief for guiding research."""

    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )


class ClarifyWithUser(BaseModel):
    """Model for user clarification requests."""

    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    questions: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )


class NewTask(BaseModel):
    """New task to add to todo list."""

    description: str = Field(description="Task description")
    source: Literal["knowledge_gap", "original_query"] = Field(
        default="knowledge_gap", description="Task source: original_query or knowledge_gap"
    )
    rationale: str = Field(description="Rationale for adding this task")


class TodoUpdates(BaseModel):
    """Updates to todo list from reflection."""

    completed_tasks: list[str] = Field(default_factory=list, description="Task IDs to mark as completed")
    cancel_tasks: list[str] = Field(default_factory=list, description="Task IDs to cancel")
    add_tasks: list[NewTask] = Field(default_factory=list, description="New tasks to add")


async def clarify_with_user(state: DeepResearchState) -> Command[Literal["write_research_brief", "__end__"]]:
    """Analyzes user messages and asks clarifying questions if the research scope is unclear.

    Args:
        state: Current deep research state containing messages

    Returns:
        Command to either end (if clarification needed) or proceed to write_research_brief
    """
    messages = state["messages"]

    prompt = CLARIFY_WITH_USER_PROMPT.format(
        messages=get_buffer_string(messages),
        date=datetime.now().strftime("%c"),
    )

    llm = get_llm(**config.supervisor_model.model_dump())
    structured_llm = llm.with_structured_output(ClarifyWithUser)
    response = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    if response.need_clarification:
        return Command(
            goto=END,
            update={"messages": [AIMessage(content=response.questions)]},
        )
    else:
        return Command(
            goto="write_research_brief",
            update={"messages": [AIMessage(content=response.verification)]},
        )


async def write_research_brief(state: DeepResearchState) -> Command[Literal["plan_research"]]:
    """Transforms user messages into a structured research brief.

    Args:
        state: Current deep research state containing messages

    Returns:
        Command to proceed to plan_research with research brief and todo manager
    """
    messages = state["messages"]

    prompt = WRITE_RESEARCH_BRIEF_PROMPT.format(
        messages=get_buffer_string(messages),
        date=datetime.now().strftime("%c"),
    )

    llm = get_llm(**config.supervisor_model.model_dump())
    structured_llm = llm.with_structured_output(ResearchQuestion)
    response = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    research_topic = response.research_brief

    todo_manager = ResearchTodoManager(research_topic=research_topic)
    logger.info(f"Initialized todo manager for research topic: {research_topic[:100]}")

    return Command(
        goto="plan_research",
        update={
            "research_brief": research_topic,
            "todo_manager": todo_manager,
            "research_iterations": 0,
        },
    )


async def plan_research(state: DeepResearchState) -> Command[Literal["execute_tasks"]]:
    """Plan research based on steering tasks.

    Args:
        state: Current state with research brief and todo manager

    Returns:
        Command to proceed to execute_tasks
    """
    research_brief = state["research_brief"]
    todo_manager = state["todo_manager"]
    research_iterations = state.get("research_iterations", 0)

    logger.info(f"Planning research iteration {research_iterations}")

    await todo_manager.prepare_for_next_loop(research_iterations)

    if not todo_manager.initial_plan_created:
        await todo_manager.create_initial_plan(
            initial_query=research_brief,
            research_context=f"Research iteration {research_iterations}",
        )
        logger.info(f"Created initial plan with {len(todo_manager.tasks)} tasks")

    pending_tasks = todo_manager.get_pending_tasks()
    if not pending_tasks:
        logger.warning("No pending tasks available")
        return Command(
            goto="execute_tasks",
            update={"research_iterations": research_iterations + 1},
        )

    top_tasks = pending_tasks[: config.MAX_TASKS_PER_ITERATION]
    logger.info(f"Selected {len(top_tasks)} of {len(pending_tasks)} pending tasks for execution")

    for task in top_tasks:
        todo_manager.mark_task_in_progress(task.id)

    return Command(
        goto="execute_tasks",
        update={"research_iterations": research_iterations + 1},
    )


async def execute_tasks(state: DeepResearchState) -> Command[Literal["process_results"]]:
    """Execute research tasks using researcher subgraph.

    Args:
        state: Current state with todo manager

    Returns:
        Command to proceed to process_results with research notes
    """
    todo_manager = state["todo_manager"]
    tasks = todo_manager.get_in_progress_tasks()[: config.MAX_CONCURRENT_RESEARCH_UNITS]

    if not tasks:
        logger.warning("No tasks in progress")
        return Command(
            goto="process_results",
            update={
                "raw_notes": [],
                "notes": [],
            },
        )

    logger.info(f"Executing {len(tasks)} research tasks in parallel")

    tasks_to_run = [
        researcher_subgraph.ainvoke(
            {
                "researcher_messages": [HumanMessage(content=task.description)],
                "research_topic": task.description,
            }
        )
        for task in tasks
    ]

    responses = await asyncio.gather(*tasks_to_run, return_exceptions=True)

    all_raw_notes = []
    all_notes = []

    for i, (response, task) in enumerate(zip(responses, tasks, strict=False)):
        if isinstance(response, Exception):
            logger.error(f"Task {i} failed with error: {response}")
            todo_manager.mark_task_cancelled(task.id, f"Error: {response}")
            continue

        content = response.get("compressed_research", "")
        raw_notes = response.get("raw_notes", [])
        all_raw_notes.extend(raw_notes)

        if content and len(content) > config.MIN_CONTENT_LENGTH:
            all_notes.append(content)
            todo_manager.mark_task_completed(task.id, f"Completed: {task.description[:50]}...")
            logger.info(f"Task {task.id} completed with {len(content)} chars of research")
        else:
            logger.warning(f"Task {task.id} returned insufficient content: {len(content)} chars")

    return Command(
        goto="process_results",
        update={
            "raw_notes": all_raw_notes,
            "notes": all_notes,
        },
    )


async def process_results(state: DeepResearchState) -> Command[Literal["reflect_on_tasks", "generate_report"]]:
    """Process research results and decide whether to continue or finish.

    Args:
        state: Current state with notes and iteration count

    Returns:
        Command to either reflect_on_tasks or generate_report
    """
    research_iterations = state.get("research_iterations", 0)
    todo_manager = state["todo_manager"]
    notes = state["notes"]

    logger.info(f"Processing results for iteration {research_iterations}")

    exceeded_iterations = research_iterations >= config.MAX_RESEARCHER_ITERATIONS
    pending = todo_manager.get_pending_tasks()
    no_pending_tasks = not pending
    completed = len([t for t in todo_manager.tasks.values() if t.status == TaskStatus.COMPLETED])

    logger.info(f"Status - {len(pending)} pending, {completed} completed tasks, {len(notes)} notes collected")

    if exceeded_iterations or no_pending_tasks:
        if exceeded_iterations:
            logger.info(f"Max iterations limit reached ({config.MAX_RESEARCHER_ITERATIONS})")
        if no_pending_tasks:
            logger.info("All tasks completed successfully")

        return Command(goto="generate_report")
    else:
        logger.info(f"Continuing research - {len(pending)} tasks remaining")
        return Command(goto="reflect_on_tasks")


async def reflect_on_tasks(state: DeepResearchState) -> Command[Literal["plan_research", "generate_report"]]:
    """Reflect on completed research and update tasks using LLM.

    Args:
        state: Current state with notes and todo manager

    Returns:
        Command to either plan_research or generate_report
    """
    todo_manager = state["todo_manager"]
    notes = state["notes"]

    if not notes:
        logger.info("No research notes available yet, skipping reflection")
        return Command(goto="plan_research")

    pending = todo_manager.get_pending_tasks()
    if not pending:
        logger.info("No pending tasks remaining, finishing research")
        return Command(goto="generate_report")

    logger.info(f"Analyzing {len(pending)} pending tasks against {len(notes)} research findings")

    llm = get_llm(**config.supervisor_model.model_dump())

    prompt = REFLECT_ON_TASKS_PROMPT.format(
        pending_tasks=todo_manager.get_pending_tasks_for_llm(),
        completed_tasks=todo_manager.get_completed_tasks_for_llm(),
        research_findings="\n".join(notes[-3:]),
    )

    structured_llm = llm.with_structured_output(TodoUpdates)
    todo_updates = await structured_llm.ainvoke([HumanMessage(content=prompt)])

    if todo_updates.completed_tasks or todo_updates.cancel_tasks or todo_updates.add_tasks:
        _process_completed_tasks(todo_manager, todo_updates)
        _process_cancelled_tasks(todo_manager, todo_updates)
        _process_new_tasks(todo_manager, todo_updates)
    else:
        logger.info("No todo updates from LLM")

    return Command(goto="plan_research")


def _process_completed_tasks(todo_manager: ResearchTodoManager, todo_updates: TodoUpdates) -> None:
    """Process completed_tasks list from LLM reflection."""
    logger.info(f"Processing {len(todo_updates.completed_tasks)} completed tasks")

    for task_id in todo_updates.completed_tasks:
        if task_id not in todo_manager.tasks:
            logger.warning(f"Task {task_id} not found")
            continue

        task = todo_manager.tasks[task_id]

        if task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]:
            todo_manager.mark_task_completed(task_id, completion_note="Addressed in research loop")
            logger.info(f"Marked task {task_id} as completed")


def _process_cancelled_tasks(todo_manager: ResearchTodoManager, todo_updates: TodoUpdates) -> None:
    """Process cancel_tasks list from LLM reflection."""
    logger.info(f"Processing {len(todo_updates.cancel_tasks)} cancelled tasks")

    for task_id in todo_updates.cancel_tasks:
        if task_id in todo_manager.tasks:
            todo_manager.mark_task_cancelled(task_id, reason="No longer relevant based on findings")
            logger.info(f"Cancelled task {task_id}")


def _process_new_tasks(todo_manager: ResearchTodoManager, todo_updates: TodoUpdates) -> None:
    """Process add_tasks list from LLM reflection."""
    SOURCE_PRIORITY = {
        "original_query": 9,
        "knowledge_gap": 7,
    }

    logger.info(f"Adding {len(todo_updates.add_tasks)} new tasks")

    for i, new_task in enumerate(todo_updates.add_tasks):
        priority = SOURCE_PRIORITY[new_task.source]

        logger.debug(f"Processing new task {i+1}/{len(todo_updates.add_tasks)}: {new_task.description[:60]}")
        task_id = todo_manager.create_task(
            description=new_task.description,
            priority=priority,
            source=new_task.source,
            created_from_message=new_task.rationale,
        )
        logger.info(f"Added task {task_id} with priority {priority} from source {new_task.source}")


async def generate_report(state: DeepResearchState) -> DeepResearchState:
    """Generates the final comprehensive research report.

    Args:
        state: Current deep research state with research brief and notes

    Returns:
        Updated state with final_report
    """
    messages = state["messages"]
    research_brief = state["research_brief"]
    notes = state["notes"]
    findings = "\n".join(notes)

    prompt = GENERATE_REPORT_PROMPT.format(
        research_task=research_brief,
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
workflow.add_node("write_research_brief", write_research_brief)
workflow.add_node("plan_research", plan_research)
workflow.add_node("execute_tasks", execute_tasks)
workflow.add_node("process_results", process_results)
workflow.add_node("reflect_on_tasks", reflect_on_tasks)
workflow.add_node("generate_report", generate_report)

workflow.add_edge(START, "clarify_with_user")
workflow.add_edge("generate_report", END)

deep_research_agent = workflow.compile(checkpointer=MemorySaver())
