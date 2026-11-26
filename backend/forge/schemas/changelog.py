"""One entry per optimizer change (Req 6), appended to changelog.jsonl."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class FieldChange(BaseModel):
    path: str
    before: Any = None
    after: Any = None
    text_diff: str | None = None


class ScoreSnapshot(BaseModel):
    overall: float
    by_category: dict[str, float] = Field(default_factory=dict)


class ChangeEntry(BaseModel):
    iteration: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    failure_class: str
    target_case_ids: list[str] = Field(default_factory=list)
    hypothesis: str = ""
    changes: list[FieldChange] = Field(default_factory=list)
    score_before: ScoreSnapshot
    score_after: ScoreSnapshot
    kept: bool
    reverted_reason: str | None = None
    agent_version_before: int
    agent_version_after: int
