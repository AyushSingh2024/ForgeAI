"""Hugging Face Space entry point (free Gradio SDK) for the ForgeAI backend.

At start-up it downloads the backend from the public GitHub repo and serves the same FastAPI app on port 7860,
with a small Gradio status page mounted at "/". In the background it installs Ollama (CPU build) and pulls the
local judge model. Until that finishes, the judge falls back to the hosted model and every report says so.

Environment (set as Space secrets/variables): OPENAI_API_KEY, API_KEY, CORS_ORIGINS. Optional: JUDGE_MODEL,
AGENT_MODEL, REPO_ZIP, SKIP_OLLAMA=1.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

WORK = Path(os.environ.get("WORK_DIR", "/tmp/forge"))
REPO_ZIP = os.environ.get("REPO_ZIP", "https://github.com/AyushSingh2024/ForgeAI/archive/refs/heads/main.zip")
OLLAMA_TGZ = os.environ.get(
    "OLLAMA_DOWNLOAD", "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst")
GPU_DIRS = ("cuda", "rocm", "vulkan", "mlx", "jetpack")  # GPU libraries are useless on a free CPU Space

DEFAULTS = {
    "LLM_PROVIDER": "openai", "AGENT_MODEL": "gpt-4o-mini",
    "JUDGE_PROVIDER": "ollama", "JUDGE_MODEL": "llama3.2:3b", "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "RUNS_DIR": str(WORK / "runs"), "BUDGET_MAX_LLM_CALLS": "450", "BUDGET_MAX_TOKENS": "500000",
    "BUDGET_MAX_SECONDS": "3600", "EVAL_TARGET_CASES": "20", "FORGE_MAX_ITERATIONS": "2",
}
for key, value in DEFAULTS.items():
    os.environ.setdefault(key, value)

STATE = {"judge": "starting"}


def _open(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "forgeai-space"}), timeout=120)


def fetch_backend() -> Path:
    """Download the repo zip and return its backend/ folder (a restart picks up newly pushed code)."""
    if os.environ.get("FORGE_BACKEND_DIR"):
        return Path(os.environ["FORGE_BACKEND_DIR"])
    src = WORK / "src"
    shutil.rmtree(src, ignore_errors=True)
    src.mkdir(parents=True, exist_ok=True)
    with _open(REPO_ZIP) as resp:
        zipfile.ZipFile(io.BytesIO(resp.read())).extractall(src)
    return next(p for p in src.glob("*/backend") if (p / "app" / "main.py").exists())


def install_ollama(root: Path) -> Path:
    exe = root / "bin" / "ollama"
    if exe.exists():
        return exe
    import zstandard

    root.mkdir(parents=True, exist_ok=True)
    with _open(OLLAMA_TGZ) as resp, zstandard.ZstdDecompressor().stream_reader(resp) as stream, \
            tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            parts = [p for p in member.name.split("/") if p not in ("", ".")]
            if any(p.startswith(GPU_DIRS) for p in parts):
                continue
            try:
                tar.extract(member, root, filter="data")
            except TypeError:  # Python < 3.11.4 has no extraction filters
                tar.extract(member, root)
    exe.chmod(0o755)
    return exe


def start_local_judge() -> None:
    """Install and start Ollama, then pull the judge model. Never stops the API if anything fails."""
    model = os.environ["JUDGE_MODEL"]
    if os.environ.get("JUDGE_PROVIDER") != "ollama" or os.environ.get("SKIP_OLLAMA") == "1":
        STATE["judge"] = "local judge disabled"
        return
    try:
        STATE["judge"] = "downloading Ollama (about 1.5 GB, a few minutes)"
        exe = install_ollama(WORK / "ollama")
        env = {**os.environ, "OLLAMA_MODELS": str(WORK / "models"), "HOME": str(WORK / "home"),
               "OLLAMA_HOST": "127.0.0.1:11434"}
        (WORK / "home").mkdir(parents=True, exist_ok=True)
        log = open(WORK / "ollama.log", "w")  # noqa: SIM115 - lives as long as the server
        subprocess.Popen([str(exe), "serve"], env=env, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(180):
            try:
                with _open("http://127.0.0.1:11434/api/version"):
                    break
            except OSError:
                time.sleep(1)
        STATE["judge"] = f"pulling {model} (about 2 GB)"
        subprocess.run([str(exe), "pull", model], env=env, check=True, timeout=1800, stdout=log,
                       stderr=subprocess.STDOUT)
        STATE["judge"] = f"ready: ollama {model} (local, inside this Space)"
    except Exception as exc:  # noqa: BLE001 - the API keeps working with the hosted fallback judge
        STATE["judge"] = f"unavailable ({exc.__class__.__name__}: {exc}); the hosted model judges instead"


backend = fetch_backend()
sys.path.insert(0, str(backend))  # must come first: the backend package is called "app"
os.chdir(backend)

import gradio as gr  # noqa: E402
import uvicorn  # noqa: E402

from app.main import app as api  # noqa: E402


def status() -> str:
    return (f"### ForgeAI backend is running\n- Local judge: **{STATE['judge']}**\n"
            f"- Agent model: `{os.environ['LLM_PROVIDER']}:{os.environ['AGENT_MODEL']}`\n"
            "- [API docs](/docs) · [health](/health)\n\n"
            "Use the web app (Vercel) to build agents. While the local judge is still downloading, "
            "runs use the hosted model as judge and say so in their report.")


with gr.Blocks(title="ForgeAI backend") as ui:
    page = gr.Markdown(status())
    gr.Button("Refresh status").click(status, outputs=page)
    ui.load(status, outputs=page)

try:
    server = gr.mount_gradio_app(api, ui, path="/", ssr_mode=False)
except TypeError:  # older Gradio without ssr_mode
    server = gr.mount_gradio_app(api, ui, path="/")

threading.Thread(target=start_local_judge, name="local-judge", daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(server, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
