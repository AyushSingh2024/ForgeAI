"""Req 7 regression: the report must render even if the template is newer than the loaded builder code
(a long-running API server keeps old Python in memory but reads the template fresh from disk)."""

from __future__ import annotations

from forge.pipeline import prepare_run, run
from forge.report import builder
from forge.report.builder import build_report
from forge.context import RunContext
from tests.test_pipeline_smoke import RESPONDER


def test_report_renders_with_and_without_actual_models(tmp_path, tiny_corpus, cfg, make_fake_hub, monkeypatch):
    hub = make_fake_hub(agent=RESPONDER, judge=RESPONDER)
    run_dir = prepare_run(tmp_path / "runs" / "rep", "Help gym members with memberships and refunds.", tiny_corpus)
    run(run_dir, cfg, mode="unattended", hub=hub)
    text = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "judge actually used `fake:" in text
    assert "status **running**" not in text

    original = builder.collect

    def without_models(ctx):
        data = original(ctx)
        data.pop("actual_models")
        return data

    monkeypatch.setattr(builder, "collect", without_models)
    out = build_report(RunContext(run_dir=run_dir, cfg=cfg, hub=hub))
    assert "judge actually used `-`" in out.read_text(encoding="utf-8")

def _rel(passed: bool, details: list[dict]):
    from forge.schemas.scorecard import JudgeReliability

    return JudgeReliability(calibration_pass=passed, calibration_passed=sum(d["passed"] for d in details),
                            calibration_total=len(details), calibration_details=details)


def test_report_says_which_judge_ran_and_why():
    local = builder.judge_info({"actual_models": {"judge": ["ollama:llama3.2:3b"], "agent": ["openai:gpt-4o-mini"]},
                                "llm": {"judge_provider": "ollama", "judge_model": "llama3.2:3b"}})
    assert local["local"] and "meets" in local["lines"][0] and "different model family" in local["lines"][1]

    hosted = builder.judge_info({"actual_models": {"judge": ["openai:gpt-4o-mini"], "agent": ["openai:gpt-4o-mini"]},
                                 "llm": {"judge_provider": "openai", "judge_model": "gpt-4o-mini"}})
    assert not hosted["local"] and hosted["same_model"]
    assert "does NOT meet" in hosted["lines"][0] and "Streamlit" in hosted["lines"][0]
    assert "self-preference" in hosted["lines"][1]

    fell_back = builder.judge_info({"actual_models": {"judge": ["openai:gpt-4o-mini"], "agent": ["openai:gpt-4o-mini"]},
                                    "llm": {"judge_provider": "ollama", "judge_model": "llama3.2:3b"}})
    assert "not reachable" in fell_back["lines"][0]


def test_failed_calibration_is_explained():
    details = [{"case": "a1", "item": "perfect", "expect": "faithfulness>=4", "got": 2, "passed": False},
               {"case": "a1", "item": "wrong_refusal", "expect": "relevance<=2", "got": None, "passed": False},
               {"case": "a1", "item": "verbosity", "expect": "padded answer must not win", "got": "A", "passed": True}]
    lines = builder.calibration_explanation(_rel(False, details),
                                            {"judge": "ollama:x", "judge_rubric_version": 2,
                                             "recheck": {"calibration_passed": 3, "calibration_total": 3,
                                                         "calibration_pass": True}})
    text = " ".join(lines)
    assert "too harsh on a correct answer" in text and "no valid scores" in text
    assert "code checks alone" in text and "3/3" in text and "NOT re-graded" in text
    assert builder.calibration_explanation(_rel(True, details[2:])) == []


def test_perfect_calibration_answer_is_the_source_sentence():
    from forge.judge.calibration import perfect_answer

    quote = "Internet costs are reimbursed up to 25 EUR per month for employees on a fully remote contract."
    assert perfect_answer(quote, ["25 EUR per month"]).startswith(quote + ' (source: "')
    assert "Second fact." in perfect_answer(quote, ["Second fact"])
