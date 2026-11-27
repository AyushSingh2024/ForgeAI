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