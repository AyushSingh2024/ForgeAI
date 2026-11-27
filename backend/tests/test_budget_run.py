"""A run must finish in one go even when the budget is tight: the reserve pays for the holdout test and report."""

from __future__ import annotations

import json

from forge.config import with_overrides
from forge.llm.budget import Budget
from forge.pipeline import STAGES, prepare_run, run
from tests.test_pipeline_smoke import RESPONDER


def test_reserve_and_can_afford(cfg):
    b = Budget(with_overrides(cfg, "budget", max_tokens=1000, max_llm_calls=100).budget)
    b.add_tokens(790)
    assert not b.can_afford(tokens=50, calls=1)     # 790 + 50 > 800 working budget (20% held back)
    b.release_reserve()
    assert b.can_afford(tokens=50, calls=1)


def test_tight_budget_still_finishes_with_a_report(tmp_path, tiny_corpus, cfg, make_fake_hub):
    tight = with_overrides(cfg, "budget", max_llm_calls=140)
    hub = make_fake_hub(agent=RESPONDER, judge=RESPONDER)
    hub.budget = Budget(tight.budget)
    for c in (hub.agent, hub.judge, hub.builder):
        c.budget = hub.budget
    run_dir = prepare_run(tmp_path / "runs" / "tight", "Help gym members with memberships and refunds.", tiny_corpus)
    status = run(run_dir, tight, mode="unattended", hub=hub)
    assert status["status"] in ("completed", "budget_stopped")
    assert (run_dir / "REPORT.md").exists()
    assert (run_dir / ".stages" / "report.done").exists()
    summary = json.loads((run_dir / "optimize_summary.json").read_text()) if (run_dir / "optimize_summary.json").exists() else {}
    if summary:
        assert "estimated_candidate_cost" in summary
    assert all((run_dir / ".stages" / f"{s}.done").exists() or status["stages"][s]["status"] in ("skipped", "failed")
               for s in STAGES)


def test_chat_answers_do_not_share_one_budget(agent_dir, cfg, make_fake_hub):
    """Regression: a long-running chat server kept one budget for every question. After the time limit (about
    32 minutes of uptime) every answer failed with 'time budget reached'. Each chat answer gets its own allowance."""
    import json

    from forge.llm.budget import CHAT_BUDGET
    from forge.runtime.runner import AgentRuntime

    reply = json.dumps({"action": "final", "answer": "Up to 5 days carry over.", "citations": [], "refused": False})
    hub = make_fake_hub(agent=lambda m, t: reply)
    rt = AgentRuntime.load(agent_dir / "agent.yaml", cfg=cfg, llm=hub.agent, per_answer_budget=CHAT_BUDGET)
    hub.budget.started_at -= 10_000  # the server has been up for hours
    hub.budget.calls = 10_000        # and has answered many questions
    ans, _ = rt.answer("How many days can carry over?")
    assert ans.answer
