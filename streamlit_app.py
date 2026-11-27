"""ForgeAI on Streamlit Community Cloud: one-file UI that calls the forge engine directly (no FastAPI needed).

Pages: browse runs (committed demo runs + builds made here), chat with any built agent, start a new build.
Secrets (Streamlit "Advanced settings → Secrets", TOML):
    OPENAI_API_KEY = "sk-..."        # required for chat and builds
    APP_PASSWORD = "..."             # optional but recommended: protects your API credit
Optional: AGENT_MODEL, JUDGE_MODEL, EMBEDDER ("hash" = lite mode if memory is tight), MAX_BUILDS_PER_DAY.

Free hosting cannot run Ollama, so on Streamlit the judge is a hosted model; the committed demo runs used a local
Ollama judge, and every report states which judge actually ran.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def _secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001 - no secrets file when running locally
        pass
    return os.environ.get(name, default)


# Configure the engine before it is imported (forge.config reads environment variables).
RUNS_DIR = Path(_secret("RUNS_DIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "forge_runs")))
for key, value in {
    "OPENAI_API_KEY": _secret("OPENAI_API_KEY"),
    "LLM_PROVIDER": _secret("LLM_PROVIDER", "openai"),
    "AGENT_MODEL": _secret("AGENT_MODEL", "gpt-4o-mini"),
    "JUDGE_PROVIDER": _secret("JUDGE_PROVIDER", "openai"),
    "JUDGE_MODEL": _secret("JUDGE_MODEL", "gpt-4o-mini"),
    "EMBEDDER": _secret("EMBEDDER", "BAAI/bge-small-en-v1.5"),
    "LLM_CACHE_PATH": str(RUNS_DIR / ".cache" / "llm.sqlite"),
    "BUDGET_MAX_LLM_CALLS": _secret("BUDGET_MAX_LLM_CALLS", "450"),
    "BUDGET_MAX_TOKENS": _secret("BUDGET_MAX_TOKENS", "500000"),
    "BUDGET_MAX_SECONDS": _secret("BUDGET_MAX_SECONDS", "2400"),
    "EVAL_TARGET_CASES": "20",
    "FORGE_MAX_ITERATIONS": "2",
}.items():
    if value:
        os.environ[key] = value
RUNS_DIR.mkdir(parents=True, exist_ok=True)

from forge.config import load_config  # noqa: E402
from forge.llm.client import make_hub  # noqa: E402
from forge.pipeline import STAGES, prepare_run, run as run_pipeline  # noqa: E402
from forge.runtime.runner import AgentRuntime  # noqa: E402

DEMO_RUNS = {d.name: d / "run" for d in sorted((BACKEND / "demos").glob("*")) if (d / "run" / "REPORT.md").exists()}
ALLOWED = ["pdf", "docx", "md", "txt", "html", "csv", "xlsx", "png", "jpg", "jpeg"]
MAX_UPLOAD_MB = 20
STAGE_LABEL = {"ingest": "Read documents", "intake": "Requirements (unattended interview)",
               "guard": "Groundability check", "generate_agent": "Generate agent", "generate_evals": "Generate tests",
               "evaluate_0": "Baseline evaluation", "optimize": "Optimize", "final_holdout": "Holdout test",
               "report": "Report"}

st.set_page_config(page_title="ForgeAI", page_icon="🛠️", layout="wide")


# --------------------------------------------------------------------------- helpers
@st.cache_resource
def build_lock() -> threading.Lock:
    return threading.Lock()


@st.cache_resource
def build_counter() -> dict:
    return {"day": "", "count": 0}


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def all_runs() -> dict[str, Path]:
    runs = {f"Demo: {name.replace('_', ' ')}": path for name, path in DEMO_RUNS.items()}
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        if d.is_dir() and (d / "REPORT.md").exists():
            runs[f"Built here: {d.name}"] = d
    return runs


def agents() -> dict[str, Path]:
    return {label: path / "agent" / "agent.yaml" for label, path in all_runs().items()
            if (path / "agent" / "agent.yaml").exists()}


def zip_run(run_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in run_dir.rglob("*"):
            rel = p.relative_to(run_dir)
            if p.is_file() and not any(part in ("index", ".extracted") or part.startswith("index_v") for part in rel.parts):
                zf.write(p, Path(run_dir.name) / rel)
    return buf.getvalue()


def pct(v) -> str:
    return "-" if v is None else f"{v:.0%}"


@st.cache_resource(show_spinner="Loading the agent (first time takes ~30 s)...")
def load_runtime(agent_yaml: str, mtime: float) -> AgentRuntime:  # mtime busts the cache after a rebuild
    return AgentRuntime.load(Path(agent_yaml), cfg=load_config())


def need_key() -> bool:
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("No OPENAI_API_KEY is configured. Add it in the app's Settings → Secrets.")
        return True
    return False


# --------------------------------------------------------------------------- password gate
password = _secret("APP_PASSWORD")
if password and not st.session_state.get("authed"):
    st.title("🛠️ ForgeAI")
    entered = st.text_input("Password", type="password")
    if entered:
        if entered == password:
            st.session_state.authed = True
            st.rerun()
        st.error("Wrong password")
    st.stop()

# --------------------------------------------------------------------------- layout
st.sidebar.title("🛠️ ForgeAI")
st.sidebar.caption("Brief + documents in, tested agent out.")
page = st.sidebar.radio("Page", ["Runs", "Chat with an agent", "Build a new agent"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(
    f"Agent model: `{os.environ.get('AGENT_MODEL')}` · Judge: `{os.environ.get('JUDGE_PROVIDER')}:"
    f"{os.environ.get('JUDGE_MODEL')}`")
st.sidebar.info("This hosted demo uses a **hosted judge** (free hosting cannot run Ollama). The committed HR and "
                "ship-spares demo runs used a **local Ollama judge** (`llama3.2:3b`); each report shows which judge ran.")
st.sidebar.markdown("[GitHub repo](https://github.com/AyushSingh2024/ForgeAI)")

# --------------------------------------------------------------------------- page: runs
if page == "Runs":
    st.title("Runs")
    runs = all_runs()
    if not runs:
        st.warning("No runs found.")
        st.stop()
    label = st.selectbox("Run", list(runs))
    run_dir = runs[label]
    status = read_json(run_dir / "status.json", {})
    report = read_json(run_dir / "report.json", {})
    best, hold, base = report.get("best") or {}, report.get("holdout") or {}, report.get("baseline") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", status.get("status", "unknown"))
    c2.metric("Baseline pass rate", pct(base.get("pass_rate")))
    c3.metric("Best (train)", pct(best.get("pass_rate")))
    c4.metric("Holdout (unseen)", pct(hold.get("pass_rate")), help=f"{hold.get('n_cases', '?')} held-out cases")
    st.download_button("Download this run (zip)", zip_run(run_dir), file_name=f"forgeai-{run_dir.name}.zip")

    tabs = st.tabs(["Report", "Requirements", "Groundability", "Agent", "Test cases", "Scores", "Changes"])
    with tabs[0]:
        st.markdown((run_dir / "REPORT.md").read_text(encoding="utf-8"))
    with tabs[1]:
        md = run_dir / "requirements.md"
        st.markdown(md.read_text(encoding="utf-8") if md.exists() else "_not available_")
    with tabs[2]:
        g = read_json(run_dir / "groundability.json", {})
        st.write(f"Coverage: **{pct(g.get('coverage'))}**")
        for w in g.get("warnings", []):
            st.warning(w)
        st.dataframe([{"ask": v["ask_text"], "verdict": v["verdict"], "tool": v.get("needed_tool") or "",
                       "evidence": v.get("explanation", "")} for v in g.get("verdicts", [])], width="stretch")
    with tabs[3]:
        y = run_dir / "agent" / "agent.yaml"
        st.code(y.read_text(encoding="utf-8") if y.exists() else "not available", language="yaml")
    with tabs[4]:
        cases = read_jsonl(run_dir / "evals" / "cases.jsonl")
        st.write(f"{len(cases)} validated cases")
        st.dataframe([{"id": c["id"], "category": c["category"], "split": c["split"], "question": c["question"],
                       "expected": c["expected_behavior"], "key facts": "; ".join(f["fact"] for f in c["key_facts"])}
                      for c in cases], width="stretch")
    with tabs[5]:
        rows = []
        for name in [str(i) for i in range(10)] + ["final_holdout"]:
            sc = read_json(run_dir / "iterations" / name / "scorecard.json")
            if sc:
                s = sc["summary"]
                rows.append({"iteration": "baseline" if name == "0" else ("holdout" if name == "final_holdout" else name),
                             "pass rate": s["pass_rate"], "key-fact coverage": s.get("key_fact_coverage"),
                             "hallucination rate": s.get("hallucination_rate"), "cases": s["n_cases"]})
        if rows:
            st.dataframe(rows, width="stretch")
            st.bar_chart({r["iteration"]: r["pass rate"] for r in rows})
    with tabs[6]:
        changes = read_jsonl(run_dir / "changelog.jsonl")
        st.write(f"Optimizer: {(read_json(run_dir / 'optimize_summary.json', {}) or {}).get('stop_reason', '-')}")
        st.dataframe([{"iter": e["iteration"], "failure class": e["failure_class"], "change": e["hypothesis"],
                       "before": e["score_before"]["overall"], "after": e["score_after"]["overall"],
                       "kept": e["kept"]} for e in changes], width="stretch")

# --------------------------------------------------------------------------- page: chat
elif page == "Chat with an agent":
    st.title("Chat with an agent")
    available = agents()
    if not available or need_key():
        st.stop()
    label = st.selectbox("Agent", list(available))
    yaml_path = available[label]
    try:
        rt = load_runtime(str(yaml_path), yaml_path.stat().st_mtime)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load this agent: {exc}")
        st.stop()
    st.caption(f"{rt.agent.name} v{rt.agent.version} · tools: {', '.join(rt.agent.tool_names()) or 'none'}")
    key = f"chat::{label}"
    history = st.session_state.setdefault(key, [])
    if not history and rt.agent.suggested_questions:
        st.caption("Try: " + " · ".join(rt.agent.suggested_questions[:3]))
    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    question = st.chat_input("Ask a question about the documents")
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"), st.spinner("Thinking..."):
            try:
                ans, trace = rt.answer(question, [{"role": m["role"], "content": m["plain"]} for m in history[-6:]])
                parts = [ans.answer]
                if ans.clarifying_question and ans.clarifying_question not in ans.answer:
                    parts.append(f"_{ans.clarifying_question}_")
                for t in ans.tool_calls:
                    parts.append(f"`{t.tool}({json.dumps(t.arguments)[:120]})`")
                if ans.citations:
                    parts.append("**Sources**\n" + "\n".join(
                        f"{i}. {c.doc_id}{f' p.{c.page}' if c.page else ''}: “{c.quote[:200]}”"
                        for i, c in enumerate(ans.citations, 1)))
                text = "\n\n".join(parts)
            except Exception as exc:  # noqa: BLE001
                text, ans = f"Error: {exc}", None
            st.markdown(text)
        history += [{"role": "user", "content": question, "plain": question},
                    {"role": "assistant", "content": text, "plain": ans.answer if ans else text}]

# --------------------------------------------------------------------------- page: build
else:
    st.title("Build a new agent")
    st.write("Upload a one-paragraph brief and the documents. The factory runs unattended (the interviewer answers "
             "its own questions conservatively and marks them as assumed). A build takes about 5 to 15 minutes; "
             "**keep this tab open** until it finishes.")
    if need_key():
        st.stop()
    brief = st.text_area("Brief", height=140,
                         placeholder="Who the assistant is for, what it must answer, and what it must refuse.")
    files = st.file_uploader("Documents", type=ALLOWED, accept_multiple_files=True)
    total_mb = sum(f.size for f in files or []) / 1024 / 1024
    limit = int(_secret("MAX_BUILDS_PER_DAY", "5"))
    counter = build_counter()
    today = datetime.now().strftime("%Y-%m-%d")
    if counter["day"] != today:
        counter.update(day=today, count=0)
    ok = 20 <= len(brief.strip()) <= 3000 and files and total_mb <= MAX_UPLOAD_MB
    st.caption(f"{len(files or [])} file(s), {total_mb:.1f} MB (max {MAX_UPLOAD_MB} MB) · "
               f"builds today: {counter['count']}/{limit}")
    if st.button("Forge the agent", type="primary", disabled=not ok):
        lock = build_lock()
        if counter["count"] >= limit:
            st.error("Daily build limit reached on this demo. Try again tomorrow, or run ForgeAI locally.")
            st.stop()
        if not lock.acquire(blocking=False):
            st.error("Another build is running right now. Please try again in a few minutes.")
            st.stop()
        try:
            counter["count"] += 1
            run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
            run_dir = RUNS_DIR / run_id
            docs = run_dir / "upload"
            docs.mkdir(parents=True)
            for f in files:
                (docs / Path(f.name).name).write_bytes(f.getvalue())
            prepare_run(run_dir, brief, docs)
            shutil.rmtree(docs, ignore_errors=True)
            cfg = load_config()
            box = st.status("Building...", expanded=True)
            started = time.time()

            def on_event(stage: str, state: str, message: str) -> None:
                if state in ("done", "failed", "skipped") or (state == "info" and message):
                    icon = {"done": "✅", "failed": "⚠️", "skipped": "⏭️"}.get(state, "•")
                    box.write(f"{icon} **{STAGE_LABEL.get(stage, stage)}** {message}")

            try:
                result = run_pipeline(run_dir, cfg, mode="unattended", on_event=on_event, hub=make_hub(cfg))
                box.update(label=f"Finished: {result.get('status')} in {(time.time() - started) / 60:.1f} min",
                           state="complete")
                st.success("Done. Open **Runs** to see the report, or **Chat with an agent** to try it.")
            except Exception as exc:  # noqa: BLE001
                box.update(label="Build failed", state="error")
                st.error(f"{exc.__class__.__name__}: {exc}")
        finally:
            lock.release()

st.sidebar.divider()
st.sidebar.caption("Stages: " + " → ".join(STAGE_LABEL[s] for s in STAGES))
