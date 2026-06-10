"""Pydantic schemas for API requests / responses."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)
    session_id: Optional[str] = None

    @validator("message")
    def _reject_injection(cls, v: str) -> str:
        try:
            from app.utils.sanitizer import detect_prompt_injection, safe_truncate
        except Exception:
            return v
        if detect_prompt_injection(v):
            raise ValueError("Message contains disallowed instructions or patterns")
        # Also truncate conservatively at the schema level
        return safe_truncate(v, max_chars=3000)


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
