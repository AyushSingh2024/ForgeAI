"""A-vs-B comparison with position-bias and verbosity defences.

Each comparison runs twice with the order swapped. Only a consistent winner counts; otherwise it is a tie.
If the winner is much longer while code-measured key-fact coverage is equal, it is a verbosity suspect -> tie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from forge.llm.client import LLMClient


class PairVerdict(BaseModel):
    rationale: str = ""
    winner: Literal["1", "2", "tie"] = "tie"


@dataclass
class PairResult:
    winner: Literal["A", "B", "tie"]
    flip_consistent: bool
    verbosity_suspect: bool = False
    raw: tuple[str, str] = ("tie", "tie")


def _ask(llm: LLMClient, question: str, context: list[str], key_facts: list[str], first: str, second: str) -> str:
    res = llm.complete("judge_pairwise", {"question": question, "context": [c[:1000] for c in context[:5]],
                                          "key_facts": key_facts, "answer_1": first[:2500], "answer_2": second[:2500]},
                       schema=PairVerdict, temperature=0.0, max_tokens=400)
    return res.data.winner if res.ok else "tie"


def compare(question: str, context: list[str], key_facts: list[str], answer_a: str, answer_b: str, llm: LLMClient,
            coverage_a: float | None = None, coverage_b: float | None = None) -> PairResult:
    v1 = _ask(llm, question, context, key_facts, answer_a, answer_b)       # A shown first
    v2 = _ask(llm, question, context, key_facts, answer_b, answer_a)       # B shown first
    m1 = {"1": "A", "2": "B", "tie": "tie"}[v1]
    m2 = {"1": "B", "2": "A", "tie": "tie"}[v2]
    consistent = m1 == m2
    winner = m1 if consistent else "tie"
    suspect = False
    if winner != "tie" and coverage_a is not None and coverage_b is not None and abs(coverage_a - coverage_b) < 1e-6:
        la, lb = len(answer_a.split()), len(answer_b.split())
        longer = "A" if la > lb else "B"
        if winner == longer and max(la, lb) > 1.5 * max(1, min(la, lb)):
            suspect, winner = True, "tie"
    return PairResult(winner=winner, flip_consistent=consistent, verbosity_suspect=suspect, raw=(v1, v2))  # type: ignore[arg-type]


def flip_agreement(results: list[PairResult]) -> float | None:
    if not results:
        return None
    return round(sum(r.flip_consistent for r in results) / len(results), 3)
