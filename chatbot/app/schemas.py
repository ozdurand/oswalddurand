"""Pydantic schemas for API requests / responses."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)
    session_id: Optional[str] = None


class SourceDocument(BaseModel):
    content: str
    metadata: dict
    score: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceDocument] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
