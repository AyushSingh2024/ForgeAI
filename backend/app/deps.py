"""Shared FastAPI dependencies and singletons."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from app.config import Settings, get_settings
from app.jobs.queue import JobQueue
from app.storage.runs_store import RunStore


@lru_cache
def get_run_store() -> RunStore:
    return RunStore(get_settings().runs_dir)


@lru_cache
def get_job_queue() -> JobQueue:
    s = get_settings()
    return JobQueue(get_run_store(), interview_timeout_min=s.interview_timeout_min)


def require_api_key(x_api_key: str | None = Header(default=None), settings: Settings = Depends(get_settings)) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(401, "missing or wrong X-API-Key")


def get_run_or_404(run_id: str, store: RunStore = Depends(get_run_store)) -> str:
    if not store.exists(run_id):
        raise HTTPException(404, f"run {run_id} not found")
    return run_id
