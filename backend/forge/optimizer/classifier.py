"""Label each failed case with ONE failure class. Ordered rules first, an LLM critic only as tie-breaker."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel

from forge.llm.client import LLMClient
from forge.schemas.eval_case import EvalCase
from forge.schemas.scorecard import CaseResult

FailureClass = Literal["retrieval_miss", "prompt_defect", "hallucination", "wrong_refusal", "false_compliance",
                       "tool_error"]
CLASSES = ("retrieval_miss", "prompt_defect", "hallucination", "wrong_refusal", "false_compliance", "tool_error")


class CriticVerdict(BaseModel):
    reasoning: str = ""
    failure_class: FailureClass = "prompt_defect"
    hypothesis: str = ""


def classify(case: EvalCase, res: CaseResult, transcript: dict[str, Any], llm: LLMClient | None = None) -> tuple[str, str]:
    """Returns (failure_class, reason)."""
    det = res.deterministic
    ans = transcript.get("answer") or {}
    refused = bool(ans.get("refused")) or (not det.refusal_correct and case.expected_behavior == "answer")
    if case.expected_behavior == "refuse" and not det.refusal_correct:
        return "false_compliance", "answered a question it must refuse"
    if not det.citation_quote_verbatim:
        return "hallucination", "cited a quote that is not in the passage"
    if not det.numbers_grounded:
        return "hallucination", f"numbers not in the context or tools: {det.details.get('ungrounded_numbers')}"
    if res.judge.faithfulness is not None and res.judge.faithfulness <= 2:
        return "hallucination", "judge: claims not supported by the context"
    if case.expected_tools and not det.tool_correct:
        return "tool_error", f"expected tools {case.expected_tools}, called {det.details.get('tools_called')}"
    if case.expected_behavior in ("answer", "clarify") and refused:
        if res.gold_in_topk is False:
            return "retrieval_miss", "refused because the source passage was not retrieved"
        return "wrong_refusal", "refused although the source passage was retrieved"
    if res.gold_in_topk is False:
        return "retrieval_miss", "the source passage was not in the top-k results"
    if res.gold_in_topk or (det.key_fact_coverage is not None and det.key_fact_coverage < 1):
        return "prompt_defect", f"passage retrieved but key facts missing (coverage {det.key_fact_coverage})"
    if llm is not None:
        r = llm.complete("critic", {"question": case.question, "expected": case.expected_behavior,
                                    "key_facts": [f.fact for f in case.key_facts], "answer": ans.get("answer", ""),
                                    "checks": det.model_dump(), "judge": res.judge.model_dump()},
                         schema=CriticVerdict, max_tokens=300)
        if r.ok:
            return r.data.failure_class, r.data.hypothesis or r.data.reasoning
    return "prompt_defect", "unclear failure (tone, format or ambiguity handling)"


def group(results: list[CaseResult]) -> dict[str, list[str]]:
    """failure_class -> failed case ids, ordered by size (the expected gain of fixing that class)."""
    g: dict[str, list[str]] = defaultdict(list)
    for r in results:
        if r.verdict == "fail" and r.failure_class:
            g[r.failure_class].append(r.case_id)
    return dict(sorted(g.items(), key=lambda kv: -len(kv[1])))
