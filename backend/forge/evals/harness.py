"""Run an agent over a set of cases with the SAME runtime used for chat (what we test is what ships)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.errors import BudgetExceeded
from forge.runtime.runner import AgentRuntime
from forge.schemas.eval_case import EvalCase
from forge.util import pmap, write_jsonl


def run_cases(rt: AgentRuntime, cases: list[EvalCase], out_path: Path | None = None) -> list[dict[str, Any]]:
    def one(c: EvalCase) -> dict[str, Any]:
        try:
            ans, trace = rt.answer(c.question)
            return {"case_id": c.id, "question": c.question, "answer": ans.model_dump(mode="json"),
                    "trace": trace, "error": trace.get("error")}
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - one broken case must not stop the evaluation
            return {"case_id": c.id, "question": c.question, "answer": None, "trace": {},
                    "error": f"{exc.__class__.__name__}: {exc}"}

    # cases are independent: answer them in parallel, keep the input order
    transcripts = pmap(one, cases, rt.cfg.llm.concurrency)
    if out_path is not None:
        write_jsonl(out_path, transcripts)
    return transcripts
