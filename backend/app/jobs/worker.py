"""Run one factory job. Never raises: every failure ends as a status the UI can show."""

from __future__ import annotations

import logging
import traceback

from app.storage.runs_store import RunStore
from forge.config import load_config
from forge.errors import AwaitingAnswers, BadInput
from forge.pipeline import run

log = logging.getLogger(__name__)


def run_job(store: RunStore, run_id: str, mode: str) -> None:
    run_dir = store.run_dir(run_id)
    if (run_dir / "CANCEL").exists():
        store.set_status(run_id, status="cancelled")
        return
    pipeline_mode = "interactive_web" if mode == "interactive" else "unattended"
    try:
        run(run_dir, load_config(), mode=pipeline_mode)
    except AwaitingAnswers:
        store.set_status(run_id, status="awaiting_answers")
    except BadInput as exc:
        store.set_status(run_id, status="failed", error=f"bad input: {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("run %s failed", run_id)
        (run_dir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        store.set_status(run_id, status="failed", error=f"{exc.__class__.__name__}: {exc}")
