"""Judge output for one iteration (Req 5), saved as iterations/<n>/scorecard.json."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DeterministicResult(BaseModel):
    schema_valid: bool = True
    citation_exists: bool = True
    citation_quote_verbatim: bool = True
    key_fact_coverage: float | None = None
    numbers_grounded: bool = True
    refusal_correct: bool = True
    clarify_correct: bool | None = None
    tool_correct: bool = True
    length_ok: bool = True
    hard_fail: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class JudgeScores(BaseModel):
    """LLM-facing schema: rationale FIRST, then scores (reason before verdict). Scores have no defaults: a
    small model that returns {} must be treated as a failed call, not silently graded 3/3/3."""
    model_config = ConfigDict(json_schema_extra=lambda s: s.__setitem__(
        "required", ["rationale", "facts_covered", "faithfulness", "relevance", "tone"]))
    rationale: str
    facts_covered: int | None = Field(default=None, ge=0)
    faithfulness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    tone: int = Field(ge=1, le=5)
    ambiguity_handling: int | None = Field(default=None, ge=1, le=5)


class JudgeResult(BaseModel):
    faithfulness: int | None = None
    relevance: int | None = None
    tone: int | None = None
    ambiguity_handling: int | None = None
    facts_covered: int | None = None
    rationale: str = ""
    judge_model: str = ""
    skipped: bool = False

    def mean(self) -> float | None:
        vals = [v for v in (self.faithfulness, self.relevance, self.tone, self.ambiguity_handling) if v is not None]
        return sum(vals) / len(vals) if vals else None


class CaseResult(BaseModel):
    case_id: str
    category: str
    split: str
    verdict: Literal["pass", "fail"]
    deterministic: DeterministicResult
    judge: JudgeResult
    failure_class: str | None = None
    failure_reason: str = ""
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    gold_in_topk: bool | None = None
    latency_ms: int = 0
    tokens: int = 0


class Summary(BaseModel):
    n_cases: int = 0
    pass_rate: float = 0.0
    mean_judge: float | None = None
    key_fact_coverage: float | None = None
    hallucination_rate: float = 0.0
    refusal_precision: float | None = None
    refusal_recall: float | None = None
    by_category: dict[str, float] = Field(default_factory=dict)


class JudgeReliability(BaseModel):
    calibration_pass: bool | None = None
    calibration_passed: int = 0
    calibration_total: int = 0
    calibration_details: list[dict[str, Any]] = Field(default_factory=list)
    flip_agreement: float | None = None
    judge_det_disagreement: float | None = None


class Scorecard(BaseModel):
    run_id: str = ""
    iteration: int = 0
    agent_version: int = 1
    split_scored: Literal["train", "holdout", "all"] = "train"
    summary: Summary = Field(default_factory=Summary)
    judge_reliability: JudgeReliability = Field(default_factory=JudgeReliability)
    cases: list[CaseResult] = Field(default_factory=list)
