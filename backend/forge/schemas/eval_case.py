"""One generated test case (Req 4), stored one per line in evals/cases.jsonl."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Category = Literal["answerable", "multi_doc", "tool", "must_refuse", "ambiguous", "edge"]
CATEGORIES: tuple[str, ...] = ("answerable", "multi_doc", "tool", "must_refuse", "ambiguous", "edge")


class KeyFact(BaseModel):
    fact: str
    kind: Literal["literal", "numeric", "semantic"] = "semantic"
    value: str | float | None = None
    unit: str | None = None


class SourceRef(BaseModel):
    doc_id: str = ""
    page: int | None = None
    chunk_id: str = ""
    quote: str = ""


class GenerationMeta(BaseModel):
    prompt_id: str = ""
    prompt_version: int = 1
    validated: bool = False
    repairs: list[str] = Field(default_factory=list)
    rejected_reason: str | None = None


class EvalCase(BaseModel):
    id: str
    category: Category
    split: Literal["train", "holdout"] = "train"
    question: str
    expected_behavior: Literal["answer", "refuse", "clarify"] = "answer"
    key_facts: list[KeyFact] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    gold_answer: str | None = None
    notes: str = ""
    generation: GenerationMeta = Field(default_factory=GenerationMeta)

    @model_validator(mode="after")
    def _consistent(self) -> "EvalCase":
        if self.category == "must_refuse":
            self.expected_behavior = "refuse"
            self.key_facts = []
        if self.category == "ambiguous" and self.expected_behavior == "answer":
            self.expected_behavior = "clarify"
        return self


# LLM-facing draft schemas (ids, splits and validation are added by code)
class CaseDraft(BaseModel):
    question: str
    expected_behavior: Literal["answer", "refuse", "clarify"] = "answer"
    key_facts: list[KeyFact] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    notes: str = ""


class CaseDraftList(BaseModel):
    cases: list[CaseDraft] = Field(default_factory=list)


class FactCheck(BaseModel):
    reasoning: str = ""
    entailed: bool = False


class PhrasedQuestion(BaseModel):
    question: str
