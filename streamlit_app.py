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
    runs = {f"Built here: {d.name}": d for d in sorted(RUNS_DIR.iterdir(), reverse=True)
            if d.is_dir() and (d / "REPORT.md").exists()}
    runs.update({f"Demo: {name.replace('_', ' ')}": path for name, path in DEMO_RUNS.items()})
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
def show_case(run_dir: Path, iteration: str, case_id: str, cases_by_id: dict) -> None:
    """Everything about one test case in one iteration: question, expected facts, answer, checks, judge."""
    sc = read_json(run_dir / "iterations" / iteration / "scorecard.json", {}) or {}
    result = next((c for c in sc.get("cases", []) if c["case_id"] == case_id), None)
    tr = next((t for t in read_jsonl(run_dir / "iterations" / iteration / "transcripts.jsonl")
               if t["case_id"] == case_id), None)
    case = cases_by_id.get(case_id, {})
    st.markdown(f"**Question:** {case.get('question', '?')}")
    st.caption(f"category {case.get('category')} · expected: {case.get('expected_behavior')} · split {case.get('split')}")
    if case.get("key_facts"):
        st.markdown("**Expected key facts**\n" + "\n".join(f"- {f['fact']}" for f in case["key_facts"]))
    for s in case.get("sources", []):
        st.caption(f"source {s['doc_id']} p.{s.get('page')}: “{s['quote'][:240]}”")
    if case.get("gold_answer"):
        st.markdown(f"**Gold answer (computed by code):** {case['gold_answer']}")
    ans = (tr or {}).get("answer") or {}
    st.markdown(f"**Agent answer** {'(refused)' if ans.get('refused') else ''}")
    st.info(ans.get("answer") or (tr or {}).get("error") or "no answer")
    for i, c in enumerate(ans.get("citations", []), 1):
        st.caption(f"[{i}] {c['doc_id']} p.{c.get('page')}: “{c['quote'][:240]}”")
    for t in ans.get("tool_calls", []):
        st.code(f"{t['tool']}({json.dumps(t['arguments'])}) -> {json.dumps(t.get('result'), default=str)[:400]}")
    if result:
        det, jr = result["deterministic"], result["judge"]
        checks = ["schema_valid", "citation_exists", "citation_quote_verbatim", "numbers_grounded", "refusal_correct",
                  "tool_correct", "length_ok"]
        st.markdown("**Code checks:** " + " · ".join(f"{'✅' if det.get(k) else '❌'} {k}" for k in checks)
                    + f" · key facts {pct(det.get('key_fact_coverage'))}")
        if not jr.get("skipped"):
            st.markdown(f"**Judge** ({jr.get('judge_model')}): faithfulness {jr.get('faithfulness')} · relevance "
                        f"{jr.get('relevance')} · tone {jr.get('tone')}")
            st.caption(jr.get("rationale", ""))
        st.markdown(f"**Verdict:** {result['verdict']}"
                    + (f" · failure class **{result['failure_class']}**: {result.get('failure_reason', '')}"
                       if result.get("failure_class") else ""))
        hits = (tr or {}).get("trace", {}).get("hits", [])
        if hits:
            with st.expander(f"Retrieved passages ({len(hits)})"):
                for i, h in enumerate(hits, 1):
                    gold = any(s["quote"][:60].lower() in h.get("text", "").lower() for s in case.get("sources", []))
                    st.markdown(f"{i}. `{h['chunk_id']}` dense {h.get('dense')} {'★ contains the gold quote' if gold else ''}")
                    st.caption(h.get("text", "")[:400])


if page == "Runs":
    st.title("Runs")
    runs = all_runs()
    if not runs:
        st.warning("No runs found.")
        st.stop()
    labels = list(runs)
    default = labels.index(st.session_state["open_run"]) if st.session_state.get("open_run") in labels else 0
    label = st.selectbox("Run", labels, index=default)
    run_dir = runs[label]
    status = read_json(run_dir / "status.json", {}) or {}
    report = read_json(run_dir / "report.json", {}) or {}
    best, hold, base = report.get("best") or {}, report.get("holdout") or {}, report.get("baseline") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", status.get("status", "unknown"))
    c2.metric("Baseline pass rate", pct(base.get("pass_rate")))
    c3.metric("Best (train)", pct(best.get("pass_rate")))
    c4.metric("Holdout (unseen)", pct(hold.get("pass_rate")), help=f"{hold.get('n_cases', '?')} held-out cases")
    with st.expander("Pipeline stages"):
        for name in STAGES:
            s = (status.get("stages") or {}).get(name, {})
            st.markdown(f"- **{STAGE_LABEL.get(name, name)}**: {s.get('status', '-')} {s.get('message', '')}")
    st.download_button("Download this run (zip)", zip_run(run_dir), file_name=f"forgeai-{run_dir.name}.zip")

    tabs = st.tabs(["Report", "Requirements", "Groundability", "Agent", "Evals", "Scores", "Changes"])

    with tabs[0]:  # ---------------------------------------------------------------- report
        st.markdown((run_dir / "REPORT.md").read_text(encoding="utf-8"))

    with tabs[1]:  # ---------------------------------------------------------- requirements
        req = read_json(run_dir / "requirements.json", {}) or {}
        if req:
            a, b, c = st.columns(3)
            a.markdown(f"**Audience**  \n{req['audience']['who']} ({req['audience']['expertise']})")
            b.markdown(f"**Tone**  \n{req['tone']['style']}, formality {req['tone']['formality']}")
            c.markdown(f"**Output**  \n{req['output_preferences']['format']}, ≤ {req['output_preferences']['max_words']} words")
            st.markdown("**In scope:** " + ("; ".join(req["scope"]["in_scope"]) or "-"))
            st.markdown("**Out of scope:** " + ("; ".join(req["scope"]["out_of_scope"]) or "-"))
            st.markdown("**Must answer**")
            st.dataframe([{"id": m["id"], "topic": m["topic"], "example question": m["example_question"]}
                          for m in req["must_answer"]], width="stretch", hide_index=True)
            st.markdown("**Must refuse**")
            st.dataframe([{"topic": m["topic"], "reason": m["reason"], "source": m["source"]}
                          for m in req["must_refuse"]], width="stretch", hide_index=True)
            st.markdown(f"**Interview ({len(req['interview'])} of max 5 questions)**")
            if req["interview"]:
                st.dataframe([{"question": t["question"], "answer": t["answer"] or "(kept default)",
                               "source": t["source"]} for t in req["interview"]], width="stretch", hide_index=True)
            else:
                st.caption("No questions were needed.")
        else:
            md = run_dir / "requirements.md"
            st.markdown(md.read_text(encoding="utf-8") if md.exists() else "_not available_")

    with tabs[2]:  # --------------------------------------------------------- groundability
        g = read_json(run_dir / "groundability.json", {}) or {}
        st.markdown(f"Coverage: **{pct(g.get('coverage'))}** of {len(g.get('verdicts', []))} asks are supported by the "
                    "documents or a tool.")
        for w in g.get("warnings", []):
            st.warning(w)
        st.dataframe([{"ask": v["ask_text"], "verdict": v["verdict"], "tool": v.get("needed_tool") or "",
                       "evidence": v.get("explanation", "")} for v in g.get("verdicts", [])],
                     width="stretch", hide_index=True)
        for v in g.get("verdicts", []):
            with st.expander(f"{v['verdict']} · {v['ask_text'][:90]}"):
                for p in v.get("probes", []):
                    st.markdown(f"- Probe: {p['question']}")
                    if p.get("supporting_quote"):
                        st.caption(f"✅ verified quote ({p.get('supporting_chunk_id')}): “{p['supporting_quote']}”")
                    else:
                        st.caption("no verified quote" + (" (the model claimed support, but the quote was not in "
                                                          "the passages)" if p.get("llm_said_supported") else ""))

    with tabs[3]:  # ----------------------------------------------------------------- agent
        y = run_dir / "agent" / "agent.yaml"
        if y.exists():
            import yaml as _yaml

            agent = _yaml.safe_load(y.read_text(encoding="utf-8"))
            versions = sorted((run_dir / "agent" / "versions").glob("agent_v*.yaml"))
            st.markdown(f"**{agent['name']}** · version v{agent['version']} ({len(versions)} version(s) saved) · "
                        f"model `{agent['model']['provider']}:{agent['model']['name']}`")
            st.markdown("**Tools**")
            if agent.get("tools"):
                st.dataframe([{"tool": t["name"], "why attached": t.get("reason", "")} for t in agent["tools"]],
                             width="stretch", hide_index=True)
            else:
                st.caption("none: documents only")
            r = agent["retrieval"]
            st.markdown(f"**Retrieval:** {r['mode']}, chunk {r['chunk_size']}/{r['chunk_overlap']}, top_k {r['top_k']}, "
                        f"bm25 weight {r['bm25_weight']}, rerank {r['rerank']}, min_score {r['min_score']}")
            for reason in r.get("reasons", []):
                st.caption(f"- {reason}")
            st.markdown("**System prompt slots**")
            for slot, text in agent["system_prompt"]["slots"].items():
                if text:
                    with st.expander(slot):
                        st.write(text)
            with st.expander("Raw agent.yaml"):
                st.code(y.read_text(encoding="utf-8"), language="yaml")
        else:
            st.caption("not available")

    cases = read_jsonl(run_dir / "evals" / "cases.jsonl")
    cases_by_id = {c["id"]: c for c in cases}
    with tabs[4]:  # ----------------------------------------------------------------- evals
        stats = read_json(run_dir / "evals" / "stats.json", {}) or {}
        cols = st.columns(len(stats.get("by_category", {})) + 1 or 1)
        for col, (cat, n) in zip(cols, (stats.get("by_category") or {}).items()):
            col.metric(cat, n)
        cols[-1].metric("rejected", f"{stats.get('rejected', 0)} ({pct(stats.get('rejection_rate'))})")
        view = st.radio("Show", ["Accepted", "Rejected"], horizontal=True, key=f"evals_view_{label}")
        if view == "Accepted":
            cat = st.selectbox("Category", ["all"] + sorted({c["category"] for c in cases}), key=f"cat_{label}")
            shown = [c for c in cases if cat == "all" or c["category"] == cat]
            st.dataframe([{"id": c["id"], "category": c["category"], "split": c["split"], "question": c["question"],
                           "expected": c["expected_behavior"],
                           "key facts": "; ".join(f["fact"] for f in c["key_facts"]),
                           "source": "; ".join(f"{s['doc_id']} p.{s.get('page')}" for s in c["sources"])}
                          for c in shown], width="stretch", hide_index=True)
        else:
            rejected = read_jsonl(run_dir / "evals" / "rejected.jsonl")
            st.dataframe([{"id": c["id"], "category": c["category"], "question": c["question"],
                           "rejected because": c["generation"].get("rejected_reason")} for c in rejected],
                         width="stretch", hide_index=True)

    with tabs[5]:  # ---------------------------------------------------------------- scores
        iters = [n for n in [str(i) for i in range(10)] + ["final_holdout"]
                 if (run_dir / "iterations" / n / "scorecard.json").exists()]
        names = {n: "baseline" if n == "0" else ("holdout" if n == "final_holdout" else f"iteration {n}") for n in iters}
        scs = {n: read_json(run_dir / "iterations" / n / "scorecard.json") for n in iters}
        if not scs:
            st.caption("No scores yet.")
        else:
            st.dataframe([{"": names[n], "pass rate": pct(s["summary"]["pass_rate"]),
                           "key-fact coverage": pct(s["summary"].get("key_fact_coverage")),
                           "hallucination rate": pct(s["summary"].get("hallucination_rate")),
                           "refusal recall": pct(s["summary"].get("refusal_recall")),
                           "mean judge": s["summary"].get("mean_judge"), "cases": s["summary"]["n_cases"]}
                          for n, s in scs.items()], width="stretch", hide_index=True)
            st.markdown("**Pass rate by iteration**")
            st.bar_chart({names[n]: s["summary"]["pass_rate"] for n, s in scs.items()})
            cats = sorted({k for s in scs.values() for k in s["summary"]["by_category"]})
            st.markdown("**Pass rate by category**")
            st.dataframe([{"category": c, **{names[n]: pct(s["summary"]["by_category"].get(c)) for n, s in scs.items()}}
                          for c in cats], width="stretch", hide_index=True)
            rel = scs[iters[0]].get("judge_reliability", {})
            st.markdown(f"**Judge reliability:** calibration {rel.get('calibration_passed')}/{rel.get('calibration_total')} "
                        f"→ {'trusted' if rel.get('calibration_pass') else 'NOT trusted (verdicts used code checks only)' if rel.get('calibration_pass') is False else 'not measured'}"
                        f" · position-swap agreement {pct(rel.get('flip_agreement'))}"
                        f" · judge vs code disagreement {pct(rel.get('judge_det_disagreement'))}")
            it = st.selectbox("Cases of", iters, format_func=lambda n: names[n], key=f"iter_{label}")
            rows = scs[it]["cases"]
            st.dataframe([{"case": r["case_id"], "category": r["category"], "verdict": r["verdict"],
                           "failure class": r.get("failure_class") or "",
                           "key facts": pct(r["deterministic"].get("key_fact_coverage")),
                           "judge": "-" if r["judge"].get("skipped") else
                           f"{r['judge'].get('faithfulness')}/{r['judge'].get('relevance')}/{r['judge'].get('tone')}"}
                          for r in rows], width="stretch", hide_index=True)
            case_id = st.selectbox("Open a case", [r["case_id"] for r in rows], key=f"case_{label}_{it}")
            with st.container(border=True):
                show_case(run_dir, it, case_id, cases_by_id)

    with tabs[6]:  # --------------------------------------------------------------- changes
        changes = read_jsonl(run_dir / "changelog.jsonl")
        summary = read_json(run_dir / "optimize_summary.json", {}) or {}
        st.markdown(f"**Optimizer stopped:** {summary.get('stop_reason', '-')}")
        if not changes:
            st.caption("No changes were tried.")
        st.dataframe([{"iter": e["iteration"], "failure class": e["failure_class"], "change": e["hypothesis"],
                       "before": pct(e["score_before"]["overall"]), "after": pct(e["score_after"]["overall"]),
                       "result": "kept" if e["kept"] else f"reverted ({e.get('reverted_reason') or 'no gain'})"}
                      for e in changes], width="stretch", hide_index=True)
        for e in changes:
            with st.expander(f"iteration {e['iteration']} · {e['failure_class']} · {'kept' if e['kept'] else 'reverted'}"):
                st.caption("Targeted cases: " + ", ".join(e["target_case_ids"]))
                for ch in e["changes"]:
                    st.markdown(f"`{ch['path']}`")
                    if ch.get("text_diff"):
                        st.code(ch["text_diff"], language="diff")
                    else:
                        st.code(f"{json.dumps(ch.get('before'), default=str)[:300]}\n→ "
                                f"{json.dumps(ch.get('after'), default=str)[:300]}")

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
                st.session_state["open_run"] = f"Built here: {run_id}"
                st.success("Done. Open **Runs** (this run is selected there) for the report, requirements, "
                           "evals, scores and changes, or **Chat with an agent** to try it.")
            except Exception as exc:  # noqa: BLE001
                box.update(label="Build failed", state="error")
                st.error(f"{exc.__class__.__name__}: {exc}")
        finally:
            lock.release()

st.sidebar.divider()
st.sidebar.caption("Stages: " + " → ".join(STAGE_LABEL[s] for s in STAGES))
