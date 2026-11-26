"""Liveness (/health, used by Render) and readiness (/api/health/deep, shown in the UI)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from forge import __version__

router = APIRouter()
_cache: dict[str, object] = {"at": 0.0, "data": None}


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/api/health/deep")
def deep(settings: Settings = Depends(get_settings)) -> dict:
    if _cache["data"] and time.time() - float(_cache["at"]) < 60:  # type: ignore[arg-type]
        return _cache["data"]  # type: ignore[return-value]
    from forge.config import load_config
    from forge.llm.client import make_hub
    from forge.retrieval.embedder import get_embedder

    checks: dict[str, dict] = {}
    try:
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.runs_dir / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        checks["storage"] = {"ok": True, "detail": str(settings.runs_dir)}
    except OSError as exc:
        checks["storage"] = {"ok": False, "detail": str(exc)}
    for p in settings.check():
        checks.setdefault("config", {"ok": False, "detail": p})
    cfg = load_config()
    try:
        emb = get_embedder(cfg.llm.embedder)
        checks["embedder"] = {"ok": True, "detail": f"{emb.backend}:{emb.name}"}
    except Exception as exc:  # noqa: BLE001
        checks["embedder"] = {"ok": False, "detail": str(exc)}
    try:
        hub = make_hub(cfg)
        for role, client in (("agent_llm", hub.agent), ("judge_llm", hub.judge)):
            ok, msg = client.health()
            checks[role] = {"ok": ok, "detail": f"{client.model_id}: {msg}"}
    except Exception as exc:  # noqa: BLE001
        checks["agent_llm"] = {"ok": False, "detail": str(exc)}
    data = {"status": "ok" if all(c["ok"] for c in checks.values()) else "degraded", "checks": checks,
            "version": __version__}
    _cache.update(at=time.time(), data=data)
    return data
