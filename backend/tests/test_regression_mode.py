"""Stretch goal: regression mode (`forge eval --against`) and the cache-only switch that makes its demo free."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from forge import cli
from forge.config import load_config, with_overrides
from forge.errors import ProviderError
from forge.evals.regression import diff_scorecards
from forge.llm.client import make_hub
from forge.pipeline import prepare_run, run
from forge.schemas.scorecard import Scorecard
from forge.util import read_json, write_json
from tests.conftest import FakeProvider
from tests.test_pipeline_smoke import RESPONDER


def _card(verdicts: dict[str, str]) -> Scorecard:
    return Scorecard.model_validate({"cases": [
        {"case_id": cid, "category": "answerable", "split": "train", "verdict": v,
         "deterministic": {}, "judge": {}, "failure_reason": "" if v == "pass" else "missed a fact"}
        for cid, v in verdicts.items()]})


def test_diff_finds_fixed_and_regressed_cases():
    d = diff_scorecards(_card({"a": "pass", "b": "fail", "c": "pass", "old_only": "pass"}),
                        _card({"a": "pass", "b": "pass", "c": "fail", "new_only": "fail"}))
    assert d["compared"] == 3 and d["fixed"] == ["b"] and d["regressed"] == ["c"]
    assert d["pass_rate_before"] == pytest.approx(0.667) and d["pass_rate_after"] == pytest.approx(0.667)
    assert d["only_in_old"] == ["old_only"] and d["only_in_new"] == ["new_only"]


def test_forge_eval_against_old_scorecard(tmp_path, tiny_corpus, cfg, make_fake_hub, monkeypatch):
    hub = make_fake_hub(agent=RESPONDER, judge=RESPONDER)
    run_dir = prepare_run(tmp_path / "runs" / "reg", "Help gym members with memberships and refunds.", tiny_corpus)
    run(run_dir, cfg, mode="unattended", hub=hub)
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "make_hub", lambda c: make_fake_hub(agent=RESPONDER, judge=RESPONDER))

    baseline = run_dir / "iterations" / "0" / "scorecard.json"
    args = ["eval", str(run_dir / "agent" / "agent.yaml"), "--cases", str(run_dir / "evals" / "cases.jsonl"),
            "--split", "train", "--against", str(baseline), "--out", str(tmp_path / "reg")]
    res = CliRunner().invoke(cli.app, args)
    assert res.exit_code == 0, res.output
    diff = read_json(tmp_path / "reg" / "regression_diff.json")
    assert diff["compared"] == len(Scorecard.model_validate(read_json(baseline)).cases) > 0
    assert (tmp_path / "reg" / "scorecard.json").exists()

    # pretend the old agent passed everything: any case failing now is a regression, and the flag fails the command
    old = read_json(baseline)
    for c in old["cases"]:
        c["verdict"] = "pass"
    write_json(tmp_path / "all_pass.json", old)
    args[args.index(str(baseline))] = str(tmp_path / "all_pass.json")
    res = CliRunner().invoke(cli.app, args + ["--fail-on-regression"])
    diff = read_json(tmp_path / "reg" / "regression_diff.json")
    assert res.exit_code == (1 if diff["regressed"] else 0), res.output
    assert diff["fixed"] == []


def test_cache_only_mode_blocks_hosted_calls_but_not_local(tmp_path):
    cfg = load_config(env={"FORGE_CACHE_ONLY": "1"})
    assert cfg.llm.cache_only
    cfg = with_overrides(cfg, "llm", cache_path=str(tmp_path / "c.sqlite"), embedder="hash")

    class Hosted(FakeProvider):
        name = "openai"

    hosted = Hosted(lambda m, t: json.dumps({"ok": 1}))
    hub = make_hub(cfg, providers={"agent": hosted, "judge": FakeProvider(), "builder": hosted})
    with pytest.raises(ProviderError, match="cache-only"):
        hub.agent.chat([{"role": "user", "content": "hi"}])
    assert hosted.calls == []                       # nothing was sent to the hosted provider
    hub.judge.chat([{"role": "user", "content": "hi"}])  # a local (free) provider still runs
