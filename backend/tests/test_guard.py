"""Req 2: the groundability guard, including the deterministic override of a lying verifier."""

from __future__ import annotations

from forge.guard import run_guard
from forge.guard.probes import tool_signals
from forge.intake import run_intake
from forge.schemas.corpus import CorpusProfile
from tests.test_intake import DRAFT
from tests.conftest import scripted


def _verify(messages):
    prompt = messages[-2]["content"] if messages[-1]["role"] == "system" else messages[-1]["content"]
    text = prompt.split("Question:", 1)[1].split("\n", 1)[0]  # only the probe question, not the passages
    if "administration fee" in text and "refund" in text.lower():
        return {"reasoning": "stated", "supported": True, "quote": "minus an administration fee of 25 EUR"}
    if "parking" in text.lower():
        # the model LIES: claims support with a quote that is not in any passage
        return {"reasoning": "yes", "supported": True, "quote": "Free parking is available for all members"}
    return {"reasoning": "no", "supported": False}


def test_guard_verdicts(make_fake_hub, make_run):
    draft = {**DRAFT, "must_answer": [
        {"id": "a", "topic": "refund fee", "example_question": "What is the administration fee on annual refunds?"},
        {"id": "b", "topic": "parking", "example_question": "Is parking free?"},
        {"id": "c", "topic": "opening hours", "example_question": "When does the sauna close?"}]}
    hub = make_fake_hub(agent=scripted([
        ("designing a question-answering assistant", draft),
        ("standing in for the person", {"answers": []}),
        ("realistic questions a user would ask", lambda m: {"probes": [m[-2]["content"].split('"')[1]]}),
        ("List each distinct piece", {"asks": [{"id": "b1", "text": "tell members the weather forecast for outdoor classes"}]}),
        ("Decide if the passages contain the answer", _verify),
    ]))
    ctx = make_run(hub)
    run_intake(ctx)
    report = run_guard(ctx)
    by = {v.ask_id: v for v in report.verdicts}
    assert by["a1"].verdict == "supported" and by["a1"].probes[0].quote_verified
    assert by["a2"].verdict == "unsupported" and by["a2"].probes[0].llm_said_supported
    assert by["b1"].verdict == "needs_tool" and by["b1"].needed_tool == "http_weather"
    assert "a2" in report.moved_to_refuse


def test_tool_signals():
    p = CorpusProfile()
    assert "http_weather" in tool_signals("What is the forecast at the port?", p)
    assert "current_date" in tool_signals("How many days until my leave expires?", p)
    assert "calculator" in tool_signals("Estimate the total cost of 12 filters", p)
