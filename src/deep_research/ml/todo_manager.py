"""
Simple Steering System for Deep Research.
Like Claude Code's todo.md but for research steering.

User sends messages during research -> Messages queued -> Converted to todo tasks
-> Agent reads before next loop
"""

import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from deep_research.ml.config import config
from deep_research.ml.prompts import INITIAL_PLAN_PROMPT, MESSAGE_TO_TASKS_PROMPT
from deep_research.ml.utils import get_llm

logger = logging.getLogger(__name__)


class TaskItem(BaseModel):
    """Single task item for research planning."""

    task_type: Literal["focus", "exclude", "prioritize", "stop_searching", "guidance"] = Field(
        default="guidance", description="Task type: focus, exclude, prioritize, stop_searching, or guidance"
    )
    description: str = Field(description="Clear, actionable task description")
    priority: int = Field(default=5, ge=1, le=10, description="Priority 1-10, higher = more important")


class InitialPlanResponse(BaseModel):
    """Structured output for initial research plan."""

    tasks: list[TaskItem] = Field(description="List of 3-5 initial research tasks")


class MessageToTasksResponse(BaseModel):
    """Structured output for parsing user messages into tasks."""

    tasks: list[TaskItem] = Field(description="List of tasks parsed from user message")


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Simple task derived from user steering message or research decomposition."""

    id: str
    description: str
    status: TaskStatus
    priority: int = 5  # 1-10, higher = more important
    source: str = "knowledge_gap"  # "original_query", "knowledge_gap", "steering_message"
    task_type: str = "guidance"  # "focus", "exclude", "prioritize", "stop_searching", "guidance"
    completed_note: str = ""


class ResearchTodoManager:
    """
    Simple todo.md manager for research steering.
    Like Claude Code's todo system but for research tasks.
    """

    def __init__(self, research_topic: str) -> None:
        self.research_topic = research_topic
        self.tasks: dict[str, Task] = {}
        self.pending_messages: list[str] = []
        self.all_user_messages: list[str] = []
        self.initial_plan_created = False
        self.research_loop_count = 0

    async def create_initial_plan(
        self,
        initial_query: str,
        research_context: str = "",
    ) -> None:
        """Create initial todo.md plan from the research query using LLM with structured output."""
        if self.initial_plan_created:
            logger.info("Initial plan already exists, skipping creation")
            return

        llm = get_llm(**config.supervisor_model.model_dump())

        planning_prompt = INITIAL_PLAN_PROMPT.format(
            research_topic=self.research_topic,
            initial_query=initial_query,
            research_context=research_context if research_context else "Starting fresh research",
        )

        structured_llm = llm.with_structured_output(InitialPlanResponse)
        response = await structured_llm.ainvoke([HumanMessage(content=planning_prompt)])

        for i, task_item in enumerate(response.tasks):
            task_id = f"initial_{i + 1}_{str(uuid.uuid4())[:8]}"
            task = Task(
                id=task_id,
                description=task_item.description,
                status=TaskStatus.PENDING,
                priority=task_item.priority,
                source="original_query",
                task_type=task_item.task_type,
            )
            self.tasks[task_id] = task
            logger.info(f"Created initial task - {task.description}")

        self.initial_plan_created = True
        logger.info(f"Initial plan created with {len(response.tasks)} tasks")

    async def add_user_message(self, message: str) -> None:
        """
        Add user steering message to queue (like Cursor's message queuing).
        Messages are processed later in process_pending_messages().
        """
        self.pending_messages.append(message)
        self.all_user_messages.append(message)
        logger.info(f"Queued user message, queue size: {len(self.pending_messages)}")

    async def process_pending_messages(self) -> None:
        """
        Convert pending user messages into actionable tasks.
        Processes all queued messages and creates tasks from them.
        """
        if not self.pending_messages:
            return

        logger.info(f"Processing {len(self.pending_messages)} pending messages")

        for message in self.pending_messages:
            tasks = await self._message_to_tasks(message)
            for task in tasks:
                self.tasks[task.id] = task
                logger.info(f"Added {task.task_type} task {task.id}")

        logger.info(f"Processed and cleared {len(self.pending_messages)} messages from queue")
        self.pending_messages.clear()

    async def prepare_for_next_loop(self, research_loop_count: int) -> None:
        """
        Process queued messages before next research loop.
        This mimics Cursor's behavior of processing user steering messages.
        """
        self.research_loop_count = research_loop_count

        logger.info(f"Preparing for research loop {research_loop_count}")
        logger.debug(f"Pending messages to process: {len(self.pending_messages)}")

        if self.pending_messages:
            logger.info(f"Processing {len(self.pending_messages)} queued messages")
            await self.process_pending_messages()
            pending_count = len(self.get_pending_tasks())
            completed_count = len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
            logger.info(f"Current state - {pending_count} pending, {completed_count} completed tasks")

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks sorted by priority (highest first)."""
        pending = [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
        return sorted(pending, key=lambda t: t.priority, reverse=True)

    def get_in_progress_tasks(self) -> list[Task]:
        """Get all in-progress tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS]

    def get_completed_tasks(self) -> list[Task]:
        """Get completed tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]

    def get_cancelled_tasks(self) -> list[Task]:
        """Get cancelled tasks."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.CANCELLED]

    def mark_task_in_progress(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.IN_PROGRESS
            logger.debug(f"Task {task_id} marked as in progress")
            return True
        return False

    def mark_task_completed(self, task_id: str, completion_note: str = "") -> bool:
        """Mark a task as completed (idempotent - safe to call multiple times)."""
        if task_id in self.tasks:
            task = self.tasks[task_id]

            if task.status == TaskStatus.COMPLETED:
                if completion_note and completion_note != task.completed_note:
                    task.completed_note = completion_note
                    logger.debug(f"Task {task_id} already completed, updated note")
                return True
            else:
                task.status = TaskStatus.COMPLETED
                task.completed_note = completion_note
                logger.info(f"Task {task_id} marked as completed")
                return True

        return False

    def mark_task_cancelled(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as cancelled."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.CANCELLED
            task.completed_note = f"Cancelled: {reason}" if reason else "Cancelled"
            logger.info(f"Task {task_id} cancelled - {reason}")
            return True
        return False

    def create_task(
        self,
        description: str,
        priority: int = 5,
        source: str = "knowledge_gap",
        created_from_message: str = "",
    ) -> str:
        """Create a new steering task and return its ID."""
        task_id = f"task_{len(self.tasks) + 1}_{str(uuid.uuid4())[:8]}"
        task = Task(
            id=task_id,
            description=description,
            status=TaskStatus.PENDING,
            priority=min(10, max(1, priority)),
            source=source,
            task_type="guidance",
        )
        self.tasks[task_id] = task
        logger.info(f"Created task {task_id} from source {source}")
        return task_id

    def _format_task_line(self, task: Task, idx: int, checkbox: str = "[ ]") -> str:
        """Format a single task line with emoji and metadata."""
        emoji = {"steering_message": "🎯", "original_query": "📋", "knowledge_gap": "🔍"}.get(task.source, "")
        source_label = {
            "steering_message": "User steering",
            "original_query": "Initial plan",
            "knowledge_gap": "Knowledge gap",
        }.get(task.source, "Unknown")

        line = f"- {checkbox} **[{idx}]** {emoji} {task.description}\n"
        line += f"  - *Source:* {source_label}\n"
        if task.completed_note:
            prefix = "Reason:" if task.status == TaskStatus.CANCELLED else ""
            line += f"  - *{prefix} {task.completed_note}*\n" if prefix else f"  - *{task.completed_note}*\n"
        line += "\n"
        return line

    def get_todo_md(self) -> str:
        """Generate todo.md content like Claude Code."""
        md = "# Research Steering Plan\n\n"
        md += f"**Topic:** {self.research_topic}\n\n"

        pending = self.get_pending_tasks()
        if pending:
            md += "## Pending\n\n"
            for idx, task in enumerate(pending, 1):
                md += self._format_task_line(task, idx, "[ ]")

        in_progress = self.get_in_progress_tasks()
        if in_progress:
            md += "## Currently Processing\n\n"
            for idx, task in enumerate(in_progress, 1):
                md += self._format_task_line(task, idx, "[ ]")

        completed = self.get_completed_tasks()
        if completed:
            md += "## Completed\n\n"
            for idx, task in enumerate(completed, 1):
                md += self._format_task_line(task, idx, "[x]")

        cancelled = [t for t in self.tasks.values() if t.status == TaskStatus.CANCELLED]
        if cancelled:
            md += "## Cancelled\n\n"
            for idx, task in enumerate(cancelled[-3:], 1):
                md += self._format_task_line(task, idx, "[~]")

        if not any([pending, in_progress, completed, cancelled]):
            md += "## 📝 No steering instructions yet\n\n"

        return md

    def get_pending_tasks_for_llm(self) -> str:
        """
        Format ONLY pending tasks for LLM reflection to decide completion.
        Clean, focused format - only what needs evaluation.
        """
        pending = self.get_pending_tasks()
        if not pending:
            return "No pending tasks - all tasks completed or cancelled."

        lines = ["PENDING TASKS TO EVALUATE FOR COMPLETION:"]
        lines.append("(Only mark as completed if research clearly addressed this task)\n")
        for task in pending:
            lines.append(f"- [{task.id}] (P{task.priority}) {task.description}")

        return "\n".join(lines)

    def get_completed_tasks_for_llm(self) -> str:
        """
        Format completed tasks for LLM when creating NEW tasks.
        Shows what's already done to avoid duplicates.
        """
        completed = self.get_completed_tasks()

        if not completed:
            return "No tasks completed yet - just starting research."

        lines = ["ALREADY COMPLETED (do NOT create duplicate tasks):"]
        for task in completed:
            lines.append(f"✓ COMPLETED: {task.description}")

        return "\n".join(lines)

    async def _message_to_tasks(self, message: str) -> list[Task]:
        """
        Convert user message to actionable research tasks using LLM parsing.
        Parses messages like "Focus on X", "Exclude Y" into structured tasks.
        """
        llm = get_llm(**config.supervisor_model.model_dump())

        parsing_prompt = MESSAGE_TO_TASKS_PROMPT.format(
            research_topic=self.research_topic,
            message=message,
        )

        structured_llm = llm.with_structured_output(MessageToTasksResponse)
        response = await structured_llm.ainvoke([HumanMessage(content=parsing_prompt)])

        tasks = []
        for task_data in response.tasks:
            task_type = task_data.task_type
            task_id = f"{task_type}_{str(uuid.uuid4())[:8]}"

            task = Task(
                id=task_id,
                description=task_data.description,
                status=TaskStatus.PENDING,
                priority=task_data.priority,
                source="steering_message",
                task_type=task_type,
            )

            tasks.append(task)
            logger.debug(f"Created {task_type} task from message")

        return tasks
