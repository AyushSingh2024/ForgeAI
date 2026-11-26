"""FastAPI entry point. Render starts it with: uvicorn app.main:app --host 0.0.0.0 --port $PORT"""

from __future__ import annotations

import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import agents, artifacts, builds, chat, health, interview, runs
from app.config import get_settings
from app.deps import get_job_queue, get_run_store, require_api_key
from forge import __version__

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("forgeai")


def install_demo_runs() -> None:
    """Copy committed demo runs (backend/demos/<name>/run) into RUNS_DIR so the hosted site always has agents."""
    settings = get_settings()
    store = get_run_store()
    if not settings.demos_dir.exists():
        return
    for demo in sorted(settings.demos_dir.iterdir()):
        src = demo / "run"
        if not (src / "REPORT.md").exists():
            continue
        run_id = f"demo-{demo.name}"
        dest = store.run_dir(run_id)
        if dest.exists():
            continue
        shutil.copytree(src, dest)
        brief = (demo / "brief.txt").read_text(encoding="utf-8") if (demo / "brief.txt").exists() else demo.name
        store._write(dest / "meta.json", {"run_id": run_id, "created_at": (dest / "REPORT.md").stat().st_mtime,
                                          "mode": "unattended", "source": "committed-demo", "brief": brief})
        st = store.status(run_id)
        if st.get("status") not in ("completed", "budget_stopped"):
            store.set_status(run_id, status="completed")
        log.info("installed demo run %s", run_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    for p in settings.check():
        log.warning("config problem: %s", p)
    try:
        install_demo_runs()
    except Exception as exc:  # noqa: BLE001
        log.warning("could not install demo runs: %s", exc)
    get_job_queue().start()
    try:
        from forge.config import load_config
        from forge.retrieval.embedder import get_embedder

        get_embedder(load_config().llm.embedder)  # warm up so the first request is not slow
    except Exception as exc:  # noqa: BLE001
        log.warning("embedder warm-up failed: %s", exc)
    yield
    get_job_queue().stop()


app = FastAPI(title="ForgeAI", version=__version__, lifespan=lifespan,
              description="Brief + documents in, tested agent out.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router)
protected = [Depends(require_api_key)]
for r in (builds.router, runs.router, interview.router, artifacts.router, agents.router, chat.router):
    app.include_router(r, dependencies=protected)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(exc)[:300]})
