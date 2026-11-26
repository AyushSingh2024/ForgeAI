"""Req 1: the intake interviewer."""

from __future__ import annotations

import pytest

from forge.errors import AwaitingAnswers
from forge.intake import run_intake
from forge.intake.questioner import select_questions
from forge.schemas.requirements import DraftMeta, RequirementsDraft
from tests.conftest import scripted

DRAFT = {"agent_name": "Gym Helper", "scope": {"in_scope": ["memberships", "refunds"]},
         "audience": {"who": "gym members", "expertise": "novice"},
         "must_answer": [{"id": "x", "topic": "membership prices", "example_question": "How much is Plus?"},
                         {"id": "y", "topic": "refunds", "example_question": "Can I get a refund?"},
                         {"id": "z", "topic": "opening hours", "example_question": "When do you open on Sunday?"}],
         "must_refuse": [{"id": "r", "topic": "medical advice", "reason": "not qualified"}],
         "confidence": {"scope": 0.3, "audience": 0.2, "tone": 0.1, "must_answer": 0.4, "must_refuse": 0.3,
                        "output_preferences": 0.1}}


def test_question_cap_is_hard():
    d = RequirementsDraft(confidence=DraftMeta(scope=0, audience=0, tone=0, must_answer=0, must_refuse=0,
                                               output_preferences=0))
    assert len(select_questions(d, max_questions=10)) == 5
    assert len(select_questions(d, max_questions=2)) == 2


def test_no_uncertain_fields_no_questions():
    d = RequirementsDraft(confidence=DraftMeta(scope=1, audience=1, tone=1, must_answer=1, must_refuse=1,
                                               output_preferences=1))
    assert select_questions(d) == []


def test_unattended_marks_assumed(make_fake_hub, make_run):
    hub = make_fake_hub(agent=scripted([("designing a question-answering assistant", DRAFT),
                                        ("standing in for the person", {"answers": []})]))
    ctx = make_run(hub)
    req = run_intake(ctx)
    assert req.interview and all(t.source == "assumed" for t in req.interview)
    assert len(req.must_answer) >= 3 and len(req.must_refuse) >= 2
    assert ctx.path("requirements.md").read_text(encoding="utf-8").startswith("# Requirements")


def test_answers_file_used(make_fake_hub, make_run):
    hub = make_fake_hub(agent=scripted([("designing a question-answering assistant", DRAFT)]))
    ctx = make_run(hub)
    ctx.path("input", "answers.yaml").write_text("- field_path: audience.expertise\n  answer: expert\n", encoding="utf-8")
    req = run_intake(ctx)
    assert req.audience.expertise == "expert"
    assert any(t.source == "answers_file" for t in req.interview)


def test_web_mode_waits_for_answers(make_fake_hub, make_run):
    hub = make_fake_hub(agent=scripted([("designing a question-answering assistant", DRAFT)]))
    ctx = make_run(hub, mode="interactive_web")
    with pytest.raises(AwaitingAnswers):
        run_intake(ctx)
    assert ctx.path("intake", "questions.json").exists()


def test_fallback_when_llm_fails(make_fake_hub, make_run):
    ctx = make_run(make_fake_hub(agent=lambda m, t: "garbage"))
    req = run_intake(ctx)
    assert len(req.must_answer) >= 3 and any(m.source == "default" for m in req.must_refuse)
