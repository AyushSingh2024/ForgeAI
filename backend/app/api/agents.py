"""List finished agents, upload any agent.yaml + docs (proves the runner is generic), and cache runtimes."""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.deps import get_run_store
from app.storage.runs_store import RunStore
from app.storage.uploads import save_uploads
from forge.cli import new_run_id
from forge.llm.budget import CHAT_BUDGET
from forge.schemas.agent_def import AgentDefinition, load_agent, save_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])
_cache: OrderedDict[str, object] = OrderedDict()
_lock = threading.Lock()
MAX_CACHED = 3


def agent_path(store: RunStore, agent_id: str) -> Path:
    try:
        p = store.run_dir(agent_id) / "agent" / "agent.yaml"
    except ValueError as exc:
        raise HTTPException(404, "agent not found") from exc
    if not p.exists():
        raise HTTPException(404, "agent not found")
    return p


def get_runtime(store: RunStore, agent_id: str):
    """LRU cache of loaded runtimes (loading an index takes seconds; Render free has little RAM)."""
    from forge.runtime.runner import AgentRuntime

    p = agent_path(store, agent_id)
    key = f"{agent_id}:{p.stat().st_mtime}"
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    rt = AgentRuntime.load(p, per_answer_budget=CHAT_BUDGET)
    with _lock:
        _cache[key] = rt
        while len(_cache) > MAX_CACHED:
            _cache.popitem(last=False)
    return rt


@router.get("")
def list_agents(store: RunStore = Depends(get_run_store)) -> list[dict]:
    out = []
    for r in store.list():
        p = store.run_dir(r["run_id"]) / "agent" / "agent.yaml"
        if not p.exists() or r["status"] not in ("completed", "budget_stopped", "uploaded"):
            continue
        try:
            a = load_agent(p)
        except Exception:  # noqa: BLE001
            continue
        out.append({"agent_id": r["run_id"], "name": a.name, "version": a.version, "description": a.description,
                    "tools": a.tool_names(), "source_run": r["run_id"], "source": r.get("source"),
                    "pass_rate": r.get("final_pass_rate"), "holdout_pass_rate": r.get("holdout_pass_rate"),
                    "suggested_questions": a.suggested_questions})
    return out


@router.get("/{agent_id}")
def get_agent(agent_id: str, store: RunStore = Depends(get_run_store)) -> dict:
    p = agent_path(store, agent_id)
    return {"agent_id": agent_id, "data": yaml.safe_load(p.read_text(encoding="utf-8"))}


@router.post("/upload", status_code=201)
async def upload_agent(agent_yaml: UploadFile = File(...), docs: list[UploadFile] = File(...),
                       store: RunStore = Depends(get_run_store), settings: Settings = Depends(get_settings)) -> dict:
    raw = await agent_yaml.read(200_000)
    try:
        agent = AgentDefinition.model_validate(yaml.safe_load(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"invalid agent.yaml: {exc}") from exc
    run_id = f"uploaded-{new_run_id()}"
    run_dir = store.create(run_id, agent.description or agent.name, "uploaded", source="upload:agent")
    agent_dir = run_dir / "agent"
    try:
        await save_uploads(agent_dir / agent.corpus.docs_dir, docs, settings.max_upload_mb)
    except HTTPException:
        store.delete(run_id)
        raise
    agent.corpus.index_dir = "index"
    save_agent(agent, agent_dir / "agent.yaml")
    store.set_status(run_id, status="uploaded")
    return {"agent_id": run_id, "name": agent.name}
