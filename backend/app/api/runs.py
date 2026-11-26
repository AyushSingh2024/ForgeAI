"""Read the state of factory runs (the frontend polls these), cancel, delete, resume."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import get_job_queue, get_run_or_404, get_run_store
from app.jobs.queue import JobQueue
from app.storage.runs_store import RunStore
from forge.pipeline import STAGES

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _detail(store: RunStore, jobs: JobQueue, run_id: str) -> dict:
    meta = store.meta(run_id)
    st = store.status(run_id)
    stages_raw = st.get("stages", {})
    stages = [{"name": s, "status": stages_raw.get(s, {}).get("status", "pending"),
               "message": stages_raw.get(s, {}).get("message", ""),
               "started_at": stages_raw.get(s, {}).get("started_at"),
               "finished_at": stages_raw.get(s, {}).get("finished_at")} for s in STAGES]
    d = store.run_dir(run_id)
    available = {name: (d / rel).exists() for name, rel in {
        "requirements": "requirements.json", "groundability": "groundability.json", "agent": "agent/agent.yaml",
        "evals": "evals/cases.jsonl", "scorecards": "iterations/0/scorecard.json", "changelog": "changelog.jsonl",
        "report": "REPORT.md"}.items()}
    return {"run_id": run_id, "brief": meta.get("brief", ""), "mode": meta.get("mode"), "source": meta.get("source"),
            "created_at": meta.get("created_at"), "status": st.get("status", "unknown"),
            "current_stage": st.get("current_stage"), "error": st.get("error"), "notes": st.get("notes", []),
            "queue_position": jobs.position(run_id), "stages": stages, "available": available}


@router.get("")
def list_runs(store: RunStore = Depends(get_run_store)) -> list[dict]:
    return store.list()


@router.get("/{run_id}")
def get_run(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store),
            jobs: JobQueue = Depends(get_job_queue)) -> dict:
    return _detail(store, jobs, run_id)


@router.get("/{run_id}/events")
async def events(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store),
                 jobs: JobQueue = Depends(get_job_queue)) -> StreamingResponse:
    async def gen():
        last = None
        for _ in range(3600):
            d = _detail(store, jobs, run_id)
            payload = json.dumps(d, default=str)
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if d["status"] in ("completed", "failed", "cancelled", "budget_stopped", "awaiting_answers"):
                break
            await asyncio.sleep(1.5)
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/{run_id}/cancel")
def cancel(run_id: str = Depends(get_run_or_404), jobs: JobQueue = Depends(get_job_queue)) -> dict:
    jobs.cancel(run_id)
    return {"run_id": run_id, "status": "cancelling"}


@router.post("/{run_id}/resume")
def resume(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store),
           jobs: JobQueue = Depends(get_job_queue)) -> dict:
    st = store.status(run_id).get("status")
    if st not in ("failed", "cancelled", "budget_stopped"):
        raise HTTPException(409, f"run is {st}; only failed, cancelled or budget-stopped runs can be resumed")
    (store.run_dir(run_id) / "CANCEL").unlink(missing_ok=True)
    jobs.resume(run_id)
    return {"run_id": run_id, "status": "queued"}


@router.delete("/{run_id}")
def delete(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store),
           jobs: JobQueue = Depends(get_job_queue)) -> dict:
    if (store.meta(run_id).get("source") or "").startswith("committed-demo"):
        raise HTTPException(403, "committed demo runs cannot be deleted")
    if run_id in jobs.active:
        raise HTTPException(409, "cancel the run before deleting it")
    store.delete(run_id)
    return {"deleted": run_id}
