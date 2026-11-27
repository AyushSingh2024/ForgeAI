"""Orchestrates all stages. Resumable (.stages/<name>.done markers) and safe to run unattended.

Each stage reads its inputs from files and writes its outputs to files. On BudgetExceeded the pipeline skips
straight to the report and says so. This file only wires stages together; it has no business logic.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig
from forge.context import EventFn, RunContext
from forge.errors import AwaitingAnswers, BadInput, BudgetExceeded, Cancelled
from forge.llm.client import LLMHub, make_hub
from forge.llm.prompts import snapshot
from forge.util import safe_replace

STAGES = ["ingest", "intake", "guard", "generate_agent", "generate_evals", "evaluate_0", "optimize",
          "final_holdout", "report"]


def _stage_fns() -> dict[str, Callable[[RunContext], Any]]:
    from forge.evals import run_generate_evals
    from forge.generator import run_generate_agent
    from forge.guard import run_guard
    from forge.ingest import run_ingest
    from forge.intake import run_intake
    from forge.optimizer.loop import run_evaluate_0, run_final_holdout, run_optimize
    from forge.report.builder import build_report

    return {"ingest": run_ingest, "intake": run_intake, "guard": run_guard, "generate_agent": run_generate_agent,
            "generate_evals": run_generate_evals, "evaluate_0": run_evaluate_0, "optimize": run_optimize,
            "final_holdout": run_final_holdout, "report": build_report}


def prepare_run(run_dir: Path, brief: str, docs_dir: Path | None = None, answers_file: Path | None = None) -> Path:
    """Create runs/<id>/input/{brief.txt, docs/, answers.yaml}."""
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "input" / "brief.txt").write_text(brief.strip(), encoding="utf-8")
    if docs_dir is not None:
        dest = run_dir / "input" / "docs"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(docs_dir, dest)
    if answers_file is not None and answers_file.exists():
        shutil.copy(answers_file, run_dir / "input" / "answers.yaml")
    return run_dir


FINAL_STAGES = {"final_holdout", "report"}


def _restore_budget(run_dir: Path, hub: LLMHub) -> None:
    """A resumed run is a new process: count what earlier attempts of this run already spent, so a rerun cannot
    silently double the budget."""
    log = run_dir / "llm_calls.jsonl"
    if not log.exists():
        return
    tokens = calls = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not rec.get("cached"):
            calls += 1
            tokens += int(rec.get("tokens_in", 0)) + int(rec.get("tokens_out", 0))
    hub.budget.restore(tokens, calls)


def _write_status(run_dir: Path, **fields: Any) -> None:
    path = run_dir / "status.json"
    cur = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cur.update(fields)
    cur["updated_at"] = time.time()
    tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(cur, indent=2, default=str), encoding="utf-8")
    safe_replace(tmp, path)


def run(run_dir: Path, cfg: ForgeConfig, mode: str = "unattended", on_event: EventFn | None = None,
        answers: dict | None = None, hub: LLMHub | None = None, from_stage: str | None = None) -> dict[str, Any]:
    """Run (or resume) the factory. Returns the final status dict."""
    run_dir = Path(run_dir)
    hub = hub or make_hub(cfg)
    hub.set_log(run_dir / "llm_calls.jsonl")
    _restore_budget(run_dir, hub)
    stage_status: dict[str, dict[str, Any]] = (json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
                                               .get("stages", {}) if (run_dir / "status.json").exists() else {})

    def emit(stage: str, status: str, message: str = "") -> None:
        if status == "info":
            stage_status.setdefault(stage, {})["message"] = message
        else:
            st = stage_status.setdefault(stage, {})
            st["status"] = status
            if status == "running":
                st["started_at"] = time.time()
            if status in ("done", "failed", "skipped"):
                st["finished_at"] = time.time()
            if message:
                st["message"] = message
        _write_status(run_dir, stages=stage_status)
        if on_event:
            on_event(stage, status, message)

    ctx = RunContext(run_dir=run_dir, cfg=cfg, hub=hub, mode=mode, on_event=emit, answers=answers)
    cfg.save(run_dir / "config.json")
    marks = run_dir / ".stages"
    marks.mkdir(exist_ok=True)
    if from_stage:
        idx = STAGES.index(from_stage)
        for s in STAGES[idx:]:
            (marks / f"{s}.done").unlink(missing_ok=True)

    fns = _stage_fns()
    _write_status(run_dir, status="running", current_stage=None, error=None)
    stopped_early: str | None = None
    try:
        for stage in STAGES:
            if (marks / f"{stage}.done").exists():
                continue
            if (run_dir / "CANCEL").exists():
                raise Cancelled("cancelled by the user")
            if stage in FINAL_STAGES:
                hub.budget.release_reserve()  # the held-back share guarantees the run can finish
            if stopped_early and stage not in FINAL_STAGES:
                emit(stage, "skipped", stopped_early)
                continue
            if stage == "final_holdout" and not (marks / "evaluate_0.done").exists():
                emit(stage, "skipped", "no baseline evaluation to compare against")
                continue
            _write_status(run_dir, current_stage=stage)
            emit(stage, "running")
            try:
                fns[stage](ctx)
            except BudgetExceeded as exc:
                stopped_early = f"budget exceeded during {stage}: {exc}"
                ctx.note(stopped_early)
                emit(stage, "failed", str(exc))
                continue
            except AwaitingAnswers:
                emit(stage, "waiting", "waiting for interview answers")
                _write_status(run_dir, status="awaiting_answers", current_stage=stage)
                raise
            (marks / f"{stage}.done").write_text(str(time.time()), encoding="utf-8")
            emit(stage, "done")
        snapshot(run_dir, hub.used_prompts)
        final = "budget_stopped" if stopped_early else "completed"
        _write_status(run_dir, status=final, current_stage=None, notes=ctx.notes)
    except AwaitingAnswers:
        raise
    except Cancelled as exc:
        _write_status(run_dir, status="cancelled", error=str(exc))
    except BadInput as exc:
        _write_status(run_dir, status="failed", error=f"bad input: {exc}")
        raise
    except Exception as exc:
        (run_dir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        _write_status(run_dir, status="failed", error=f"{exc.__class__.__name__}: {exc}")
        raise
    return json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
