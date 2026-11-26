"""The agent's output contract ("answer_v1"), enforced by the runtime."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel):
    doc_id: str
    page: int | None = None
    chunk_id: str | None = None
    quote: str = ""


class ToolCallRecord(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None


class AgentAnswer(BaseModel):
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    clarifying_question: str | None = None
    confidence: float = 0.5


class ModelAnswer(BaseModel):
    """What the model itself is asked to return (tool calls are recorded by the runtime, not the model)."""
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    clarifying_question: str | None = None
    confidence: float = 0.5

    @field_validator("confidence", mode="before")
    @classmethod
    def _lenient_confidence(cls, v: Any) -> float:
        """Small models sometimes copy the placeholder ("0.0-1.0") or write "high"; never fail the answer on it."""
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return {"high": 0.8, "medium": 0.5, "low": 0.2}.get(str(v).strip().lower(), 0.5)

    @field_validator("answer", mode="before")
    @classmethod
    def _answer_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return v if isinstance(v, str) else str(v)
