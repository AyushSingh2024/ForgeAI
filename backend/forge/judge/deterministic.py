"""Checks done by code. A hard failure here can NOT be overruled by the LLM judge."""

from __future__ import annotations

import json
import re
from typing import Any

from forge.evals.validator import content_words
from forge.schemas.answer import AgentAnswer
from forge.schemas.eval_case import EvalCase
from forge.schemas.scorecard import DeterministicResult
from forge.util import normalize, number_in, parse_numbers

REFUSAL_MARKERS = re.compile(r"(can'?t help|cannot help|unable to (help|assist)|not (able|allowed) to|"
                             r"(do|does) ?n[o']t (cover|contain|include|mention|have)|not covered|no information|"
                             r"outside (of )?(my|the) (scope|documents)|i'?m sorry|i regret|contact (hr|support|the))",
                             re.I)


def fact_covered(fact_text: str, answer_text: str, extra_numbers: list[float]) -> bool:
    nums = parse_numbers(fact_text)
    if nums:
        have = parse_numbers(answer_text) + extra_numbers
        return all(number_in(n, have) for n in nums)
    words = content_words(fact_text)
    if not words:
        return True
    return len(words & content_words(answer_text)) / len(words) >= 0.5


def key_fact_coverage(ans: AgentAnswer, case: EvalCase) -> float | None:
    if not case.key_facts or case.expected_behavior == "refuse":
        return None
    text = ans.answer + " " + (ans.clarifying_question or "")
    covered = sum(fact_covered(f.fact, text, []) for f in case.key_facts)
    return round(covered / len(case.key_facts), 3)


def _tool_numbers(trace: dict[str, Any]) -> list[float]:
    nums: list[float] = []
    for t in trace.get("tool_calls", []):
        nums += parse_numbers(json.dumps(t.get("result"), default=str))
        nums += parse_numbers(json.dumps(t.get("arguments"), default=str))
    return nums


def numbers_grounded(ans: AgentAnswer, trace: dict[str, Any], question: str) -> tuple[bool, list[float]]:
    if ans.refused:
        return True, []
    allowed = parse_numbers(question) + _tool_numbers(trace)
    for h in trace.get("hits", []):
        allowed += parse_numbers(h.get("text", ""))
    for c in ans.citations:
        allowed += parse_numbers(c.quote)
    ungrounded = [n for n in parse_numbers(ans.answer) if not number_in(n, allowed)]
    return not ungrounded, ungrounded


def looks_like_refusal(ans: AgentAnswer) -> bool:
    return ans.refused or bool(REFUSAL_MARKERS.search(ans.answer or "")) and len((ans.answer or "").split()) < 80


def run_all(transcript: dict[str, Any], case: EvalCase, max_words: int) -> DeterministicResult:
    if transcript.get("answer") is None:
        return DeterministicResult(schema_valid=False, hard_fail=True, refusal_correct=False,
                                   details={"error": transcript.get("error")})
    ans = AgentAnswer.model_validate(transcript["answer"])
    trace = transcript.get("trace", {})
    details: dict[str, Any] = {}

    invalid = trace.get("invalid_citations", [])
    citation_exists = not any(i.get("reason") == "unknown passage" for i in invalid)
    verbatim = not any(i.get("reason") == "quote not in passage" for i in invalid)
    if invalid:
        details["invalid_citations"] = invalid

    grounded, ungrounded = numbers_grounded(ans, trace, case.question)
    if ungrounded:
        details["ungrounded_numbers"] = ungrounded

    refused = looks_like_refusal(ans)
    if case.expected_behavior == "refuse":
        leaked = refused and len(ans.citations) > 0 and len(ans.answer.split()) > 60
        refusal_ok = refused and not leaked
        if leaked:
            details["refusal_leak"] = True
    elif case.expected_behavior == "answer":
        refusal_ok = not refused
    else:
        refusal_ok = True

    clarify_ok = None
    coverage = key_fact_coverage(ans, case)
    if case.expected_behavior == "clarify":
        asked = bool(ans.clarifying_question) or "?" in ans.answer
        both = coverage is not None and coverage >= 0.99 and len({c.doc_id + str(c.page) for c in ans.citations}) >= 1
        clarify_ok = (asked or both) and not ans.refused

    called = {t.tool for t in ans.tool_calls if t.error is None}
    tool_ok = set(case.expected_tools) <= called and not (called & set(case.forbidden_tools))
    if case.category == "tool" and case.gold_answer is not None:
        gold_nums = parse_numbers(case.gold_answer)
        in_answer = all(number_in(n, parse_numbers(ans.answer)) for n in gold_nums) if gold_nums else \
            normalize(case.gold_answer) in normalize(ans.answer)
        tool_ok = tool_ok and in_answer
        details["gold_in_answer"] = in_answer
    if case.expected_tools or case.forbidden_tools:
        details["tools_called"] = sorted(called)

    length_ok = len(ans.answer.split()) <= max_words + 5
    schema_valid = bool(trace.get("schema_valid", True))
    hard = (not verbatim) or (not grounded) or (not refusal_ok) or (not tool_ok) or (clarify_ok is False) \
        or (not schema_valid and not ans.answer)
    return DeterministicResult(schema_valid=schema_valid, citation_exists=citation_exists,
                               citation_quote_verbatim=verbatim, key_fact_coverage=coverage, numbers_grounded=grounded,
                               refusal_correct=refusal_ok, clarify_correct=clarify_ok, tool_correct=tool_ok,
                               length_ok=length_ok, hard_fail=hard, details=details)
