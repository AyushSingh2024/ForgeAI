"""Rubric scoring by a local small open model (a DIFFERENT family from the agent), for what code can't check.

Anti-bias rules: rationale before scores; "length is not quality"; the judge sees KEY FACTS (not a full reference
answer); the answer is anonymised (no model name, no iteration number); temperature 0, fixed seed, cached.
"""

from __future__ import annotations

from forge.llm.client import LLMClient
from forge.schemas.scorecard import JudgeResult, JudgeScores


def judge_case(question: str, answer_text: str, context: list[str], key_facts: list[str], tone: str,
               ambiguous: bool, llm: LLMClient) -> JudgeResult:
    res = llm.complete("judge_rubric", {"question": question, "answer": answer_text.strip()[:3000],
                                        "context": [c[:1600] for c in context[:5]], "key_facts": key_facts,
                                        "tone": tone, "ambiguous": ambiguous},
                       schema=JudgeScores, temperature=0.0, max_tokens=500)
    if not res.ok:
        return JudgeResult(skipped=True, rationale=f"judge failed: {res.error}", judge_model=llm.model_id)
    s: JudgeScores = res.data
    return JudgeResult(faithfulness=s.faithfulness, relevance=s.relevance, tone=s.tone,
                       ambiguity_handling=s.ambiguity_handling if ambiguous else None,
                       facts_covered=min(s.facts_covered, len(key_facts)) if s.facts_covered is not None else None,
                       rationale=s.rationale[:600],
                       judge_model=llm.model_id)
