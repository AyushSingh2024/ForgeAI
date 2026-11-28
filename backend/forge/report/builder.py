"""Stage "report" (Req 7): the honest report. Every number comes from the JSON artifacts.

The LLM only writes two short narrative paragraphs from the numbers it is given; if the narrative contains a
number that is not in the data, it is thrown away and a plain deterministic summary is used instead.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from forge.context import RunContext
from forge.errors import BudgetExceeded
from forge.optimizer import changelog
from forge.report.charts import category_table, pass_rate_chart
from forge.schemas.agent_def import load_agent
from forge.schemas.eval_case import EvalCase
from forge.schemas.groundability import GroundabilityReport
from forge.schemas.requirements import Requirements
from forge.schemas.scorecard import Scorecard
from forge.util import number_in, parse_numbers, read_json, read_jsonl, write_json

_TEMPLATES = Path(__file__).resolve().parent / "templates"


class Narrative(BaseModel):
    summary: str = ""
    limitations: str = ""


def _sc(path: Path) -> Scorecard | None:
    data = read_json(path)
    return Scorecard.model_validate(data) if data else None


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.0%}"


def collect(ctx: RunContext) -> dict[str, Any]:
    p = ctx.path
    req = Requirements.model_validate(read_json(p("requirements.json"), {}))
    guard = GroundabilityReport.model_validate(read_json(p("groundability.json"), {}))
    agent = load_agent(p("agent", "agent.yaml")) if p("agent", "agent.yaml").exists() else None
    cases = read_jsonl(p("evals", "cases.jsonl"), EvalCase)
    stats = read_json(p("evals", "stats.json"), {})
    sc0 = _sc(p("iterations", "0", "scorecard.json"))
    opt = read_json(p("optimize_summary.json"), {})
    iters = []
    if sc0:
        iters.append(("baseline", sc0))
    for i in range(1, 10):
        s = _sc(p("iterations", str(i), "scorecard.json"))
        if s:
            iters.append((f"iter {i}", s))
    best = iters[-1][1] if iters else None
    holdout = _sc(p("iterations", "final_holdout", "scorecard.json"))
    entries = changelog.read(ctx.run_dir)
    calls = read_jsonl(p("llm_calls.jsonl"))
    notes = p("notes.txt").read_text(encoding="utf-8").splitlines() if p("notes.txt").exists() else []
    status = read_json(p("status.json"), {})
    if status.get("status") == "running":  # the report is the last stage, written before the final status
        stopped = any(n.startswith("budget exceeded") for n in notes)
        status = {**status, "status": "budget_stopped" if stopped else "completed"}
    config = read_json(p("config.json"), {})
    by_id = {c.id: c for c in cases}

    failures = []
    for label, sc in (("holdout", holdout), ("train", best)):
        if not sc:
            continue
        for r in sc.cases:
            if r.verdict == "fail" and r.case_id in by_id:
                c = by_id[r.case_id]
                failures.append({"split": label, "id": c.id, "category": c.category, "question": c.question,
                                 "expected": c.expected_behavior, "failure_class": r.failure_class or "-",
                                 "reason": r.failure_reason, "facts": "; ".join(f.fact for f in c.key_facts)})
    cost = {"llm_calls": len(calls), "cached": sum(1 for c in calls if c.get("cached")),
            "failed": sum(1 for c in calls if not c.get("ok")),
            "tokens": sum(int(c.get("tokens_in", 0)) + int(c.get("tokens_out", 0)) for c in calls),
            "by_role": dict(Counter(c.get("role", "?") for c in calls)),
            "elapsed_s": round(calls[-1]["ts"] - calls[0]["ts"], 1) if len(calls) > 1 else 0}
    actual = {role: sorted({c.get("model", "?") for c in calls if c.get("role") == role}) for role in ("agent", "judge")}
    return {"actual_models": actual, "req": req, "guard": guard, "agent": agent, "cases": cases, "stats": stats, "sc0": sc0, "iters": iters,
            "best": best, "holdout": holdout, "entries": entries, "failures": failures, "cost": cost, "notes": notes,
            "status": status, "opt": opt, "llm": config.get("llm", {})}


def _family(model_id: str) -> str:
    from forge.llm.client import _family as fam

    return fam(model_id.split(":", 1)[-1])


def judge_info(d: dict[str, Any]) -> dict[str, Any]:
    """Which judge actually graded this run, and what that means for the assignment's local-judge rule.

    Taken from llm_calls.jsonl (what really ran), compared with config.json (what was asked for)."""
    used = d.get("actual_models", {}).get("judge", [])
    agents = d.get("actual_models", {}).get("agent", [])
    llm = d.get("llm", {})
    configured = f"{llm.get('judge_provider', '?')}:{llm.get('judge_model', '?')}"
    judge = used[0] if used else None
    local = bool(judge) and judge.split(":", 1)[0] == "ollama"
    same_model = bool(judge) and judge in agents
    same_fam = bool(judge) and any(_family(judge) == _family(a) for a in agents)
    lines: list[str] = []
    if not judge:
        lines.append("No judge call was logged in this run, so it is not known which judge would have graded it.")
    elif local:
        lines.append(f"The judge was `{judge}`, a small open model running locally through Ollama. This meets the "
                     "assignment's rule that the judge is a local small open model.")
    elif configured.startswith("ollama:"):
        lines.append(f"The configured judge was the local `{configured}`, but it was not reachable, so this run fell "
                     f"back to the hosted `{judge}`. This run does NOT meet the local-judge rule; start Ollama and "
                     "run `forge doctor` before building.")
    else:
        lines.append(f"The judge was the hosted `{judge}`, not a local model, because this run was configured with a "
                     "hosted judge. The hosted Streamlit app always runs this way: its free host (Streamlit Community "
                     "Cloud) cannot run Ollama. This run does NOT meet the rule that the judge is a local small open "
                     "model; build locally with Ollama for that.")
    if judge and agents:
        if same_model:
            lines.append(f"The judge is the same model as the agent (`{agents[0]}`), so the different-family defence "
                         "against self-preference does not apply; answers are still anonymised and the code checks "
                         "are unaffected.")
        elif same_fam:
            lines.append("The judge is from the same model family as the agent, so self-preference bias is only "
                         "partly limited (answers are anonymised).")
        else:
            lines.append(f"The agent was `{', '.join(agents)}`: a different model family from the judge, which limits "
                         "self-preference bias.")
    return {"judge": judge, "configured": configured, "local": local, "same_model": same_model, "lines": lines}


_CALIBRATION_MEANING = {
    "perfect": "scored a correct, fully supported answer below 4 for faithfulness (too harsh on a correct answer)",
    "fluent_hallucination": "did not catch an answer with one number changed (faithfulness above 2)",
    "verbosity": "preferred the padded answer over the short correct one",
    "wrong_refusal": "did not penalise a refusal of an answerable question (relevance above 2)",
}


def calibration_explanation(rel: Any, recheck: dict[str, Any] | None = None) -> list[str]:
    """Plain-language reading of the calibration details: what failed, and what that did to the verdicts.

    `recheck` is an optional judge_calibration_recheck.json: the calibration re-run later with newer probes or a newer
    judge prompt (demos/scripts/recheck_calibration.py). It is reported next to the original, never instead of it."""
    if rel is None or rel.calibration_pass is None:
        return []
    failed = [c for c in rel.calibration_details if not c.get("passed")]
    out = []
    for c in failed:
        if c.get("got") is None:
            out.append(f"On `{c['case']}` ({c['item']}) the judge returned no valid scores, which counts as a failure.")
        else:
            out.append(f"On `{c['case']}` the judge {_CALIBRATION_MEANING.get(c['item'], 'gave an unexpected score')} "
                       f"(got {c['got']}).")
    if rel.calibration_pass is False:
        out.append("Because calibration failed, the LLM judge's scores were ignored for this run: every verdict was "
                   "decided by the code checks alone. Key-fact coverage then comes from word and number matching "
                   "only, with no credit for paraphrase, so correct answers worded differently from the key facts "
                   "can fail, while faithfulness is only checked by code (verbatim quotes, grounded numbers). Read these pass "
                   "rates as code-check results, not as judge-graded scores.")
    elif failed:
        out.append("Calibration still passed (at least 75% of the checks), so the judge's scores were used.")
    r = (recheck or {}).get("recheck")
    if r and r.get("calibration_total"):
        out.append(f"Re-check after this run with the revised probes (`judge_calibration_recheck.json`, judge prompt version "
                   f"{recheck.get('judge_rubric_version')}, same judge `{recheck.get('judge')}`): "
                   f"{r['calibration_passed']}/{r['calibration_total']} checks passed "
                   f"({'trusted' if r.get('calibration_pass') else 'not trusted'}). The scores above were NOT "
                   "re-graded: they are exactly what this run produced.")
    return out


def _numbers_ok(text: str, allowed: list[float]) -> bool:
    return all(number_in(n, allowed) or n in (1, 2, 3) for n in parse_numbers(text))


def narrative(ctx: RunContext, d: dict[str, Any]) -> Narrative:
    facts = {
        "baseline_train_pass_rate_pct": round(d["sc0"].summary.pass_rate * 100) if d["sc0"] else None,
        "best_train_pass_rate_pct": round(d["best"].summary.pass_rate * 100) if d["best"] else None,
        "holdout_pass_rate_pct": round(d["holdout"].summary.pass_rate * 100) if d["holdout"] else None,
        "n_cases": len(d["cases"]), "n_holdout": sum(c.split == "holdout" for c in d["cases"]),
        "changes_tried": len(d["entries"]), "changes_kept": sum(e.kept for e in d["entries"]),
        "unsupported_asks": len(d["guard"].moved_to_refuse),
        "judge_calibration_passed": d["best"].judge_reliability.calibration_pass if d["best"] else None,
        "known_failures": len(d["failures"]), "notes": d["notes"][:8],
    }
    fallback = Narrative(
        summary=(f"The factory built '{d['req'].agent_name}' and tested it on {facts['n_cases']} generated cases. "
                 f"Train pass rate went from {_pct(d['sc0'].summary.pass_rate if d['sc0'] else None)} to "
                 f"{_pct(d['best'].summary.pass_rate if d['best'] else None)} after {facts['changes_kept']} kept "
                 f"change(s); on the {facts['n_holdout']} held-out cases it scored "
                 f"{_pct(d['holdout'].summary.pass_rate if d['holdout'] else None)}."),
        limitations=("The eval cases were generated by a language model from the same documents, so they can share "
                     "its blind spots; the judge is a small model; results on a small eval set are noisy."))
    try:
        res = ctx.hub.builder.complete("report_narrative", {"facts": facts}, schema=Narrative, max_tokens=500)
    except BudgetExceeded:  # the report must always be written, even when the run used up its budget
        return fallback
    if not res.ok:
        return fallback
    allowed = [float(v) for v in facts.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    n: Narrative = res.data
    if not (n.summary and _numbers_ok(n.summary, allowed) and _numbers_ok(n.limitations, allowed)):
        return fallback
    return n


def _saved_narrative(ctx: RunContext) -> Narrative | None:
    saved = read_json(ctx.path("report.json"), {}).get("narrative")
    return Narrative.model_validate(saved) if saved and saved.get("summary") else None


def build_report(ctx: RunContext, reuse_narrative: bool = False) -> Path:
    """Write REPORT.md. reuse_narrative=True keeps the narrative saved in report.json (no model call), so an older
    run's report can be re-rendered with a newer template without changing its wording or costing anything."""
    d = collect(ctx)
    n = (_saved_narrative(ctx) if reuse_narrative else None) or narrative(ctx, d)
    # a re-render keeps the run's original id (demo runs were copied into folders named "run")
    run_id = (read_json(ctx.path("report.json"), {}).get("run_id") if reuse_narrative else None) or ctx.run_id
    d["judge_info"] = judge_info(d)
    d["calibration_explanation"] = calibration_explanation(d["best"].judge_reliability if d["best"] else None,
                                                           read_json(ctx.path("judge_calibration_recheck.json"), None))
    points = [(label, sc.summary.pass_rate) for label, sc in d["iters"]]
    if d["holdout"]:
        points.append(("holdout", d["holdout"].summary.pass_rate))
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), trim_blocks=True, lstrip_blocks=True)
    env.filters["pct"] = _pct
    env.filters["cell"] = lambda s: str(s or "").replace("|", "/").replace("\n", " ")
    md = env.get_template("report.md.j2").render(
        d=d, n=n, run_id=run_id, chart=pass_rate_chart(points),
        categories=category_table(d["sc0"], d["best"], d["holdout"]) if d["sc0"] and d["best"] else "",
        changes=changelog.to_markdown_table(d["entries"]))
    out = ctx.path("REPORT.md")
    out.write_text(md, encoding="utf-8")
    write_json(ctx.path("report.json"), {
        "run_id": run_id, "agent_name": d["req"].agent_name, "narrative": n.model_dump(),
        "points": [{"label": label, "pass_rate": v} for label, v in points],
        "baseline": d["sc0"].summary.model_dump() if d["sc0"] else None,
        "best": d["best"].summary.model_dump() if d["best"] else None,
        "holdout": d["holdout"].summary.model_dump() if d["holdout"] else None,
        "judge_reliability": d["best"].judge_reliability.model_dump() if d["best"] else None,
        "known_failures": d["failures"], "cost": d["cost"], "notes": d["notes"], "optimize": d["opt"],
        "judge_used": {k: v for k, v in d["judge_info"].items() if k != "lines"}})
    ctx.emit("report", "info", "REPORT.md written")
    return out
