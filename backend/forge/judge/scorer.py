"""Combine deterministic checks + the LLM judge into the per-iteration Scorecard.

Verdict = pass only if there is no hard deterministic failure AND key-fact coverage >= threshold AND (judge mean
>= threshold, unless the judge failed its calibration, in which case the deterministic checks decide alone).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from forge.judge.calibration import run_calibration
from forge.judge.deterministic import looks_like_refusal, run_all
from forge.judge.llm_judge import judge_case
from forge.judge.pairwise import flip_agreement
from forge.llm.client import LLMHub
from forge.config import ForgeConfig
from forge.optimizer.classifier import classify
from forge.schemas.answer import AgentAnswer
from forge.schemas.corpus import Chunk
from forge.schemas.eval_case import EvalCase
from forge.schemas.scorecard import CaseResult, JudgeReliability, JudgeResult, Scorecard, Summary
from forge.util import pmap, quote_in_text, read_json, write_json


def gold_in_topk(case: EvalCase, transcript: dict[str, Any]) -> bool | None:
    if not case.sources:
        return None
    hits = transcript.get("trace", {}).get("hits", [])
    return any(quote_in_text(s.quote, h.get("text", "")) for s in case.sources for h in hits)


def summarize(results: list[CaseResult], cases: dict[str, EvalCase]) -> Summary:
    n = len(results)
    if n == 0:
        return Summary()
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_cat[r.category].append(r.verdict == "pass")
    judge_means = [m for r in results if (m := r.judge.mean()) is not None]
    covs = [r.deterministic.key_fact_coverage for r in results if r.deterministic.key_fact_coverage is not None]
    halluc = sum((not r.deterministic.citation_quote_verbatim) or (not r.deterministic.numbers_grounded) or
                 r.failure_class == "hallucination" for r in results)
    expected_refuse = [r for r in results if cases[r.case_id].expected_behavior == "refuse"]
    refused = [r for r in results if r.deterministic.details.get("refused")]
    tp = sum(1 for r in refused if cases[r.case_id].expected_behavior == "refuse")
    return Summary(n_cases=n, pass_rate=round(sum(r.verdict == "pass" for r in results) / n, 3),
                   mean_judge=round(sum(judge_means) / len(judge_means), 3) if judge_means else None,
                   key_fact_coverage=round(sum(covs) / len(covs), 3) if covs else None,
                   hallucination_rate=round(halluc / n, 3),
                   refusal_precision=round(tp / len(refused), 3) if refused else None,
                   refusal_recall=round(tp / len(expected_refuse), 3) if expected_refuse else None,
                   by_category={k: round(sum(v) / len(v), 3) for k, v in sorted(by_cat.items())})


def calibration_for_run(run_dir: Path, cases: list[EvalCase], chunks_by_id: dict[str, Chunk], hub: LLMHub,
                        tone: str) -> JudgeReliability:
    """Run the judge calibration once per run and cache it."""
    path = run_dir / "judge_calibration.json"
    cached = read_json(path)
    if cached:
        return JudgeReliability.model_validate(cached)
    info, pairs = run_calibration(cases, chunks_by_id, hub.judge, tone)
    rel = JudgeReliability(**info, flip_agreement=flip_agreement(pairs))
    write_json(path, rel)
    return rel


def score_iteration(*, run_id: str, iteration: int, agent_version: int, cases: list[EvalCase],
                    transcripts: list[dict[str, Any]], hub: LLMHub, cfg: ForgeConfig, max_words: int, tone: str,
                    reliability: JudgeReliability, split: str = "train", out_path: Path | None = None) -> Scorecard:
    by_id = {c.id: c for c in cases}
    trusted_judge = reliability.calibration_pass is not False
    results: list[CaseResult] = []
    disagreements = 0
    judged = 0

    def checks_and_judge(t: dict[str, Any]):
        case = by_id[t["case_id"]]
        det = run_all(t, case, max_words)
        ans = AgentAnswer.model_validate(t["answer"]) if t.get("answer") else None
        det.details["refused"] = bool(ans and looks_like_refusal(ans))
        jr = JudgeResult(skipped=True, rationale="skipped")
        if ans and not det.hard_fail and case.expected_behavior != "refuse":
            ctx = [h.get("text", "") for h in t.get("trace", {}).get("hits", [])]
            jr = judge_case(case.question, ans.answer + ("\n" + ans.clarifying_question if ans.clarifying_question else ""),
                            ctx, [f.fact for f in case.key_facts], tone, case.expected_behavior == "clarify", hub.judge)
        return case, det, jr

    # the judge calls are independent per case: run them in parallel, then aggregate in order as before
    for t, (case, det, jr) in zip(transcripts, pmap(checks_and_judge, transcripts, cfg.llm.concurrency)):
        cov = det.key_fact_coverage
        if cov is not None and jr.facts_covered is not None and case.key_facts and trusted_judge:
            # word/number matching misses paraphrases ("more than three days" vs "from the 4th day");
            # the judge's paraphrase-aware count can raise coverage, never lower it
            cov = max(cov, round(jr.facts_covered / len(case.key_facts), 3))
            det.details["coverage_code"] = det.key_fact_coverage
            det.key_fact_coverage = cov
        mean = jr.mean()
        det_pass = not det.hard_fail and (cov is None or cov >= cfg.judge.pass_key_fact_coverage)
        judge_pass = mean is None or mean >= cfg.judge.pass_judge_mean or not trusted_judge
        if mean is not None:
            judged += 1
            disagreements += int(det_pass != (mean >= cfg.judge.pass_judge_mean))
        verdict = "pass" if det_pass and judge_pass else "fail"
        trace = t.get("trace", {})
        res = CaseResult(case_id=case.id, category=case.category, split=case.split, verdict=verdict, deterministic=det,
                         judge=jr, retrieved_chunk_ids=[h.get("chunk_id", "") for h in trace.get("hits", [])],
                         gold_in_topk=gold_in_topk(case, t), latency_ms=int(trace.get("latency_ms", 0) or 0),
                         tokens=int(trace.get("tokens", 0) or 0))
        if verdict == "fail":
            res.failure_class, res.failure_reason = classify(case, res, t, None)
        results.append(res)

    rel = reliability.model_copy(update={"judge_det_disagreement": round(disagreements / judged, 3) if judged else None})
    sc = Scorecard(run_id=run_id, iteration=iteration, agent_version=agent_version, split_scored=split,  # type: ignore[arg-type]
                   summary=summarize(results, by_id), judge_reliability=rel, cases=results)
    if out_path is not None:
        write_json(out_path, sc)
    return sc
