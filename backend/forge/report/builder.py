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


def build_report(ctx: RunContext) -> Path:
    d = collect(ctx)
    n = narrative(ctx, d)
    points = [(label, sc.summary.pass_rate) for label, sc in d["iters"]]
    if d["holdout"]:
        points.append(("holdout", d["holdout"].summary.pass_rate))
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), trim_blocks=True, lstrip_blocks=True)
    env.filters["pct"] = _pct
    env.filters["cell"] = lambda s: str(s or "").replace("|", "/").replace("\n", " ")
    md = env.get_template("report.md.j2").render(
        d=d, n=n, run_id=ctx.run_id, chart=pass_rate_chart(points),
        categories=category_table(d["sc0"], d["best"], d["holdout"]) if d["sc0"] and d["best"] else "",
        changes=changelog.to_markdown_table(d["entries"]))
    out = ctx.path("REPORT.md")
    out.write_text(md, encoding="utf-8")
    write_json(ctx.path("report.json"), {
        "run_id": ctx.run_id, "agent_name": d["req"].agent_name, "narrative": n.model_dump(),
        "points": [{"label": label, "pass_rate": v} for label, v in points],
        "baseline": d["sc0"].summary.model_dump() if d["sc0"] else None,
        "best": d["best"].summary.model_dump() if d["best"] else None,
        "holdout": d["holdout"].summary.model_dump() if d["holdout"] else None,
        "judge_reliability": d["best"].judge_reliability.model_dump() if d["best"] else None,
        "known_failures": d["failures"], "cost": d["cost"], "notes": d["notes"], "optimize": d["opt"]})
    ctx.emit("report", "info", "REPORT.md written")
    return out
