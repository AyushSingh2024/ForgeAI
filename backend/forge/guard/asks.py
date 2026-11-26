"""List every concrete 'ask' the agent is expected to handle (must-answer topics + explicit asks in the brief)."""

from __future__ import annotations

from rapidfuzz import fuzz

from forge.llm.client import LLMClient
from forge.schemas.groundability import Ask, AskList
from forge.schemas.requirements import Requirements
from forge.util import normalize


def extract_asks(brief: str, req: Requirements, llm: LLMClient) -> list[tuple[Ask, str]]:
    """Returns (ask, source) pairs, de-duplicated."""
    out: list[tuple[Ask, str]] = []
    for m in req.must_answer:
        text = m.topic if not m.example_question else f"{m.topic}: {m.example_question}"
        out.append((Ask(id=m.id, text=text), "must_answer"))
    res = llm.complete("guard_extract_asks", {"brief": brief, "must_answer": [m.topic for m in req.must_answer]},
                       schema=AskList, max_tokens=700)
    if res.ok:
        for i, a in enumerate(res.data.asks[:10]):
            if not a.text.strip():
                continue
            if any(fuzz.token_set_ratio(normalize(a.text), normalize(x.text)) > 80 for x, _ in out):
                continue
            out.append((Ask(id=f"b{i + 1}", text=a.text.strip()), "brief"))
    return out
