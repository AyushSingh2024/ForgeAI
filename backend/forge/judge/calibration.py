"""Check that the judge itself is trustworthy on THIS run, using answers built by code with known quality.

Items: a perfect answer, a fluent hallucination (one number changed), a correct answer padded with filler
(must not beat the short correct one in a position-swapped pairwise comparison), and a wrong refusal.
If the judge fails them, verdicts fall back to the deterministic checks only, and the report says so.
"""

from __future__ import annotations

import re
from typing import Any

from forge.judge.llm_judge import judge_case
from forge.judge.pairwise import PairResult, compare
from forge.llm.client import LLMClient
from forge.schemas.corpus import Chunk
from forge.schemas.eval_case import EvalCase

FILLER = ("It is worth noting that this is an important topic and many people ask about it. "
          "Policies like this exist to make things clear and fair for everyone involved. "
          "Please always read the relevant documentation carefully and keep it in mind. ")


def _perturb_number(text: str) -> str | None:
    m = re.search(r"\d+(?:\.\d+)?", text)
    if not m:
        return None
    n = float(m.group(0))
    new = str(int(n * 2 + 3)) if n.is_integer() else f"{n * 2 + 3:.1f}"
    return text[:m.start()] + new + text[m.end():]


def run_calibration(cases: list[EvalCase], chunks_by_id: dict[str, Chunk], llm: LLMClient,
                    tone: str) -> tuple[dict[str, Any], list[PairResult]]:
    details = []
    pairs: list[PairResult] = []
    cand = [c for c in cases if c.category == "answerable" and c.sources and c.sources[0].chunk_id in chunks_by_id]
    for case in cand[:2]:
        ctx = [chunks_by_id[s.chunk_id].text for s in case.sources if s.chunk_id in chunks_by_id]
        facts = [f.fact for f in case.key_facts]
        perfect = " ".join(facts) + f' (source: "{case.sources[0].quote[:200]}")'
        r = judge_case(case.question, perfect, ctx, facts, tone, False, llm)
        details.append({"case": case.id, "item": "perfect", "expect": "faithfulness>=4", "got": r.faithfulness,
                        "passed": (r.faithfulness or 0) >= 4})
        wrong = _perturb_number(perfect)
        if wrong:
            r = judge_case(case.question, wrong, ctx, facts, tone, False, llm)
            details.append({"case": case.id, "item": "fluent_hallucination", "expect": "faithfulness<=2",
                            "got": r.faithfulness, "passed": (r.faithfulness or 5) <= 2})
        padded = FILLER + perfect + " " + FILLER
        pr = compare(case.question, ctx, facts, perfect, padded, llm, 1.0, 1.0)
        pairs.append(pr)
        details.append({"case": case.id, "item": "verbosity", "expect": "padded answer must not win",
                        "got": pr.winner, "flip_consistent": pr.flip_consistent, "passed": pr.winner != "B"})
        r = judge_case(case.question, "I'm sorry, I can't help with that.", ctx, facts, tone, False, llm)
        details.append({"case": case.id, "item": "wrong_refusal", "expect": "relevance<=2", "got": r.relevance,
                        "passed": (r.relevance or 5) <= 2})
    passed = sum(d["passed"] for d in details)
    total = len(details)
    ok = None if total == 0 else passed >= max(1, round(total * 0.75))
    return {"calibration_pass": ok, "calibration_passed": passed, "calibration_total": total,
            "calibration_details": details}, pairs
