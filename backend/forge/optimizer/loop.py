"""Stage "optimize" (Req 6): the critic-optimizer loop.

Per iteration: classify the failures of the best version so far -> for the largest failure class, apply ONE
targeted fix -> re-run the TRAIN split -> keep the candidate only if it scores better (ties broken by a
position-swapped pairwise judge), otherwise revert and try the next class. Max 3 iterations. Every attempt,
kept or reverted, is logged with before/after scores. The holdout split is never used here.
"""

from __future__ import annotations

from typing import Any

from forge.context import RunContext
from forge.evals.harness import run_cases
from forge.judge.pairwise import compare
from forge.judge.scorer import calibration_for_run, score_iteration
from forge.optimizer import changelog
from forge.optimizer.fixers import FIXERS
from forge.optimizer.classifier import group
from forge.runtime.prompting import render_system_prompt
from forge.runtime.runner import AgentRuntime
from forge.schemas.agent_def import AgentDefinition, diff, load_agent, save_agent
from forge.schemas.changelog import ChangeEntry, FieldChange, ScoreSnapshot
from forge.schemas.corpus import Chunk
from forge.schemas.eval_case import EvalCase
from forge.schemas.requirements import Requirements
from forge.schemas.scorecard import Scorecard
from forge.util import read_json, read_jsonl, read_model, write_json


def snapshot(sc: Scorecard) -> ScoreSnapshot:
    return ScoreSnapshot(overall=sc.summary.pass_rate, by_category=sc.summary.by_category)


def field_changes(a: AgentDefinition, b: AgentDefinition) -> list[FieldChange]:
    out = []
    for d in diff(a, b):
        td = changelog.text_diff(str(d["before"]), str(d["after"])) if isinstance(d["after"], str) and \
            len(str(d["after"])) > 60 else None
        out.append(FieldChange(path=d["path"], before=d["before"], after=d["after"], text_diff=td))
    return out


class Evaluator:
    """Runs an agent version on a split and scores it (shared by evaluate_0, optimize and final_holdout)."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.req = read_model(ctx.path("requirements.json"), Requirements)
        self.cases: list[EvalCase] = read_jsonl(ctx.path("evals", "cases.jsonl"), EvalCase)
        chunks = read_jsonl(ctx.path("corpus", "chunks.jsonl"), Chunk)
        self.chunks_by_id = {c.chunk_id: c for c in chunks}
        self.tone = f"{self.req.tone.style} (formality {self.req.tone.formality}) for {self.req.audience.who}"
        self._reliability = None

    def reliability(self):
        if self._reliability is None:
            self._reliability = calibration_for_run(self.ctx.run_dir, self.cases, self.chunks_by_id, self.ctx.hub,
                                                    self.tone)
        return self._reliability

    def split(self, name: str) -> list[EvalCase]:
        return [c for c in self.cases if c.split == name] if name != "all" else list(self.cases)

    def evaluate(self, agent: AgentDefinition, iteration: int, split: str, out_dir) -> tuple[Scorecard, list[dict]]:
        ctx = self.ctx
        rt = AgentRuntime.load(agent, agent_dir=ctx.path("agent"), cfg=ctx.cfg, llm=ctx.hub.agent,
                               rewrite_llm=ctx.hub.builder)
        cases = self.split(split)
        transcripts = run_cases(rt, cases, out_dir / "transcripts.jsonl")
        sc = score_iteration(run_id=ctx.run_id, iteration=iteration, agent_version=agent.version, cases=cases,
                             transcripts=transcripts, hub=ctx.hub, cfg=ctx.cfg,
                             max_words=agent.output_contract.max_words, tone=self.tone,
                             reliability=self.reliability(), split=split, out_path=out_dir / "scorecard.json")
        return sc, transcripts


def run_evaluate_0(ctx: RunContext) -> Scorecard:
    ev = Evaluator(ctx)
    agent = load_agent(ctx.path("agent", "agent.yaml"))
    sc, _ = ev.evaluate(agent, 0, "train", ctx.path("iterations", "0"))
    ctx.emit("evaluate_0", "info", f"baseline train pass rate {sc.summary.pass_rate:.0%} on {sc.summary.n_cases} cases")
    return sc


def _pairwise_tiebreak(ev: Evaluator, ids: list[str], old_t: dict[str, dict], new_t: dict[str, dict]) -> bool:
    """True if the candidate wins a majority of position-swapped comparisons on the targeted cases."""
    wins = losses = 0
    by_id = {c.id: c for c in ev.cases}
    for cid in ids[:6]:
        a, b = old_t.get(cid, {}).get("answer"), new_t.get(cid, {}).get("answer")
        if not a or not b:
            continue
        case = by_id[cid]
        ctxs = [h.get("text", "") for h in new_t[cid].get("trace", {}).get("hits", [])]
        r = compare(case.question, ctxs, [f.fact for f in case.key_facts], a.get("answer", ""), b.get("answer", ""),
                    ev.ctx.hub.judge)
        wins += r.winner == "B"
        losses += r.winner == "A"
    return wins > losses


def run_optimize(ctx: RunContext) -> AgentDefinition:
    ev = Evaluator(ctx)
    ocfg = ctx.cfg.optimizer
    best = load_agent(ctx.path("agent", "agent.yaml"))
    best_sc = Scorecard.model_validate(read_json(ctx.path("iterations", "0", "scorecard.json")))
    best_t = {t["case_id"]: t for t in read_jsonl(ctx.path("iterations", "0", "transcripts.jsonl"))}
    tried: set[str] = set()
    history: list[dict[str, Any]] = [{"iteration": 0, "pass_rate": best_sc.summary.pass_rate, "agent_version": best.version}]
    stop_reason = f"reached max iterations ({ocfg.max_iterations})"
    by_id = {c.id: c for c in ev.cases}

    for it in range(1, ocfg.max_iterations + 1):
        if best_sc.summary.pass_rate >= ocfg.target_pass_rate:
            stop_reason = f"target pass rate {ocfg.target_pass_rate:.0%} reached"
            break
        groups = group(best_sc.cases)
        if not groups:
            stop_reason = "no fixable failures left"
            break
        if ctx.hub.budget.remaining_fraction() < 0.15:
            stop_reason = "budget nearly used up"
            break
        kept = False
        attempted = False
        it_dir = ctx.path("iterations", str(it))
        for cls, ids in groups.items():
            failed = [{"case": by_id[i], "result": next(r for r in best_sc.cases if r.case_id == i),
                       "transcript": best_t.get(i, {})} for i in ids if i in by_id]
            fix = FIXERS[cls](best, failed, tried, ctx.hub.builder)
            if fix is None:
                continue
            cand, hypothesis, key = fix
            tried.add(key)
            attempted = True
            cand.system_prompt.rendered = render_system_prompt(cand)
            ctx.emit("optimize", "info", f"iteration {it}/{ocfg.max_iterations}: {cls} -> {hypothesis}")
            sc, transcripts = ev.evaluate(cand, it, "train", it_dir / "candidates" / f"v{cand.version}_{cls}")
            new_t = {t["case_id"]: t for t in transcripts}
            better = sc.summary.pass_rate > best_sc.summary.pass_rate
            tie_win = (not better and sc.summary.pass_rate == best_sc.summary.pass_rate and
                       _pairwise_tiebreak(ev, ids, best_t, new_t))
            keep = better or tie_win or not ocfg.revert_on_regress and sc.summary.pass_rate >= best_sc.summary.pass_rate
            entry = ChangeEntry(iteration=it, failure_class=cls, target_case_ids=ids, hypothesis=hypothesis,
                                changes=field_changes(best, cand), score_before=snapshot(best_sc),
                                score_after=snapshot(sc), kept=bool(keep),
                                reverted_reason=None if keep else ("score went down" if sc.summary.pass_rate <
                                                                   best_sc.summary.pass_rate else "no improvement"),
                                agent_version_before=best.version, agent_version_after=cand.version)
            changelog.append(ctx.run_dir, entry)
            save_agent(cand, ctx.path("agent", "versions", f"agent_v{cand.version}.yaml"))
            if keep:
                best, best_sc, best_t = cand, sc, new_t
                write_json(it_dir / "scorecard.json", sc)
                kept = True
                break
            if ctx.hub.budget.remaining_fraction() < 0.15:
                break
        history.append({"iteration": it, "pass_rate": best_sc.summary.pass_rate, "agent_version": best.version,
                        "kept_change": kept})
        if not attempted:
            stop_reason = "no untried fixes left for the remaining failures"
            break

    save_agent(best, ctx.path("agent", "agent.yaml"))
    write_json(ctx.path("optimize_summary.json"), {"stop_reason": stop_reason, "history": history,
                                                    "best_version": best.version,
                                                    "best_train_pass_rate": best_sc.summary.pass_rate})
    ctx.emit("optimize", "info", f"best version v{best.version}, train pass rate {best_sc.summary.pass_rate:.0%} "
                                 f"({stop_reason})")
    return best


def run_final_holdout(ctx: RunContext) -> Scorecard:
    ev = Evaluator(ctx)
    agent = load_agent(ctx.path("agent", "agent.yaml"))
    split = "holdout" if ev.split("holdout") else "train"
    sc, _ = ev.evaluate(agent, 99, split, ctx.path("iterations", "final_holdout"))
    ctx.emit("final_holdout", "info", f"holdout pass rate {sc.summary.pass_rate:.0%} on {sc.summary.n_cases} unseen cases")
    return sc
