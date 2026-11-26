"""Output of the intake interviewer (Req 1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AnswerSource = Literal["user", "answers_file", "assumed", "default"]


class Scope(BaseModel):
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class Audience(BaseModel):
    who: str = "general users"
    expertise: Literal["novice", "intermediate", "expert"] = "intermediate"


class Tone(BaseModel):
    style: str = "clear and professional"
    formality: Literal["low", "medium", "high"] = "medium"
    language: str = "en"


class MustAnswer(BaseModel):
    id: str
    topic: str
    example_question: str = ""
    priority: int = Field(default=2, ge=1, le=3)


class MustRefuse(BaseModel):
    id: str
    topic: str
    reason: str = ""
    source: Literal["brief", "guard", "default", "user"] = "brief"


class OutputPreferences(BaseModel):
    format: Literal["prose", "bullets", "table"] = "prose"
    max_words: int = 200
    citations_required: bool = True


class InterviewTurn(BaseModel):
    question_id: str
    field_path: str
    question: str
    why_asked: str = ""
    answer: str = ""
    source: AnswerSource = "assumed"


class Requirements(BaseModel):
    run_id: str = ""
    brief: str = ""
    agent_name: str = "Assistant"
    scope: Scope = Field(default_factory=Scope)
    audience: Audience = Field(default_factory=Audience)
    tone: Tone = Field(default_factory=Tone)
    must_answer: list[MustAnswer] = Field(default_factory=list)
    must_refuse: list[MustRefuse] = Field(default_factory=list)
    output_preferences: OutputPreferences = Field(default_factory=OutputPreferences)
    interview: list[InterviewTurn] = Field(default_factory=list, max_length=5)
    assumptions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- drafting
class DraftMeta(BaseModel):
    """Confidence the drafter has in each top-level field (0 = pure guess, 1 = stated in the brief)."""
    scope: float = 0.5
    audience: float = 0.5
    tone: float = 0.5
    must_answer: float = 0.5
    must_refuse: float = 0.5
    output_preferences: float = 0.5
    notes: str = ""


class RequirementsDraft(BaseModel):
    agent_name: str = "Assistant"
    scope: Scope = Field(default_factory=Scope)
    audience: Audience = Field(default_factory=Audience)
    tone: Tone = Field(default_factory=Tone)
    must_answer: list[MustAnswer] = Field(default_factory=list)
    must_refuse: list[MustRefuse] = Field(default_factory=list)
    output_preferences: OutputPreferences = Field(default_factory=OutputPreferences)
    confidence: DraftMeta = Field(default_factory=DraftMeta)


class Question(BaseModel):
    id: str
    field_path: str
    text: str
    why: str = ""
    kind: Literal["yes_no", "choice", "free_text"] = "free_text"
    options: list[str] = Field(default_factory=list)
    default: str = ""


class QuestionList(BaseModel):
    questions: list[Question] = Field(default_factory=list)
