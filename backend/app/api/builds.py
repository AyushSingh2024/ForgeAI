"""Start a new factory run (upload) or a run on a committed demo."""

from __future__ import annotations

import shutil
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.deps import get_job_queue, get_run_store
from app.jobs.queue import JobQueue
from app.storage.runs_store import RunStore
from app.storage.uploads import save_brief, save_uploads
from forge.cli import new_run_id

router = APIRouter(prefix="/api/builds", tags=["builds"])


@router.post("", status_code=202)
async def create_build(brief: str = Form(...), files: list[UploadFile] = File(...),
                       mode: Literal["interactive", "unattended"] = Form("interactive"),
                       answers_yaml: UploadFile | None = File(None),
                       store: RunStore = Depends(get_run_store), jobs: JobQueue = Depends(get_job_queue),
                       settings: Settings = Depends(get_settings)) -> dict:
    brief = brief.strip()
    if not 20 <= len(brief) <= 3000:
        raise HTTPException(400, "the brief must be between 20 and 3000 characters")
    run_id = new_run_id()
    run_dir = store.create(run_id, brief, mode)
    try:
        await save_uploads(run_dir / "input" / "docs", files, settings.max_upload_mb)
        save_brief(run_dir, brief)
        if answers_yaml is not None:
            data = await answers_yaml.read(200_000)
            (run_dir / "input" / "answers.yaml").write_bytes(data)
    except HTTPException:
        store.delete(run_id)
        raise
    jobs.submit(run_id, mode)
    return {"run_id": run_id, "status": "queued", "links": {"run": f"/api/runs/{run_id}"}}


@router.post("/demo/{demo_name}", status_code=202)
def demo_build(demo_name: str, mode: Literal["interactive", "unattended"] = "unattended",
               store: RunStore = Depends(get_run_store), jobs: JobQueue = Depends(get_job_queue),
               settings: Settings = Depends(get_settings)) -> dict:
    demo = settings.demos_dir / demo_name
    if not (demo / "brief.txt").exists() or not (demo / "docs").exists() or "/" in demo_name or ".." in demo_name:
        raise HTTPException(404, f"demo {demo_name} not found")
    brief = (demo / "brief.txt").read_text(encoding="utf-8")
    run_id = f"{new_run_id()}-{demo_name}"
    run_dir = store.create(run_id, brief, mode, source=f"demo:{demo_name}")
    shutil.copytree(demo / "docs", run_dir / "input" / "docs")
    save_brief(run_dir, brief)
    if (demo / "answers.yaml").exists():
        shutil.copy(demo / "answers.yaml", run_dir / "input" / "answers.yaml")
    jobs.submit(run_id, mode)
    return {"run_id": run_id, "status": "queued", "links": {"run": f"/api/runs/{run_id}"}}


@router.get("/demos")
def list_demos(settings: Settings = Depends(get_settings)) -> list[dict]:
    out = []
    if settings.demos_dir.exists():
        for d in sorted(settings.demos_dir.iterdir()):
            if (d / "brief.txt").exists():
                out.append({"name": d.name, "brief": (d / "brief.txt").read_text(encoding="utf-8")[:600],
                            "has_committed_run": (d / "run" / "REPORT.md").exists()})
    return out
