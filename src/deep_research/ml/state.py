import operator
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class DeepResearchState(TypedDict):
    """Main agent state containing messages and research data."""

    messages: Annotated[list[AnyMessage], add_messages]
    research_brief: str
    raw_notes: Annotated[list[str], operator.add]
    notes: Annotated[list[str], operator.add]
    final_report: str
    todo_manager: Any
    research_iterations: int


class ResearcherState(TypedDict):
    """State for individual researchers conducting research."""

    researcher_messages: Annotated[list[AnyMessage], add_messages]
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], operator.add]
    tool_call_iterations: int
