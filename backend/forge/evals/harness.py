"""Run an agent over a set of cases with the SAME runtime used for chat (what we test is what ships)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.errors import BudgetExceeded
from forge.runtime.runner import AgentRuntime
from forge.schemas.eval_case import EvalCase
from forge.util import write_jsonl


def run_cases(rt: AgentRuntime, cases: list[EvalCase], out_path: Path | None = None) -> list[dict[str, Any]]:
    transcripts = []
    for c in cases:
        try:
            ans, trace = rt.answer(c.question)
            transcripts.append({"case_id": c.id, "question": c.question, "answer": ans.model_dump(mode="json"),
                                "trace": trace, "error": trace.get("error")})
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - one broken case must not stop the evaluation
            transcripts.append({"case_id": c.id, "question": c.question, "answer": None, "trace": {},
                                "error": f"{exc.__class__.__name__}: {exc}"})
    if out_path is not None:
        write_jsonl(out_path, transcripts)
    return transcripts
