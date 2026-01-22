"""API request and response schemas for Deep Research."""

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Start a new research session."""

    query: str = Field(..., description="The research query or topic to investigate")


class ResearchResponse(BaseModel):
    """Response when starting research."""

    session_id: str = Field(..., description="Unique session ID for this research")
    stream_url: str = Field(..., description="URL to connect for streaming updates")
    message: str = Field(..., description="Status message")


class MessageRequest(BaseModel):
    """Send a message to an active research session."""

    session_id: str = Field(..., description="Session ID from research start")
    message: str = Field(..., description="Your message (clarification answer or steering)")


class MessageResponse(BaseModel):
    """Response after sending a message."""

    success: bool = Field(..., description="Whether the message was processed")
    message: str = Field(..., description="Status message")
