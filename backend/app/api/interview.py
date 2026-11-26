"""The intake interview (Req 1) over HTTP. The pipeline pauses with status awaiting_answers until answered."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import get_job_queue, get_run_or_404, get_run_store
from app.jobs.queue import JobQueue
from app.storage.runs_store import RunStore

router = APIRouter(prefix="/api/runs/{run_id}/interview", tags=["interview"])


class Answers(BaseModel):
    answers: dict[str, str]


def _questions(store: RunStore, run_id: str) -> list[dict]:
    p = store.path_for(run_id, "questions")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@router.get("")
def get_questions(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    return {"status": store.status(run_id).get("status"), "questions": _questions(store, run_id)}


def _save_and_resume(store: RunStore, jobs: JobQueue, run_id: str, payload: dict) -> dict:
    if store.status(run_id).get("status") != "awaiting_answers":
        raise HTTPException(409, "this run is not waiting for answers")
    p = store.run_dir(run_id) / "intake" / "answers.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    jobs.resume(run_id)
    return {"run_id": run_id, "status": "queued"}


@router.post("")
def submit(body: Answers, run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store),
           jobs: JobQueue = Depends(get_job_queue)) -> dict:
    ids = {q["id"] for q in _questions(store, run_id)}
    unknown = set(body.answers) - ids
    if unknown:
        raise HTTPException(400, f"unknown question ids: {sorted(unknown)}")
    return _save_and_resume(store, jobs, run_id, {k: v.strip()[:500] for k, v in body.answers.items()})


@router.post("/skip")
def skip(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store),
         jobs: JobQueue = Depends(get_job_queue)) -> dict:
    return _save_and_resume(store, jobs, run_id, {"__skip__": True})
