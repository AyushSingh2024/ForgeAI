"""The generic runtime (Req 8) with a hand-written agent.yaml and a scripted fake model."""

from __future__ import annotations

import json

import pytest

from forge.runtime.runner import AgentRuntime
from forge.schemas.agent_def import ToolBinding, load_agent
from tests.conftest import last_user


def test_handwritten_agent_answers_with_citation(agent_dir, cfg, make_fake_hub):
    def model(messages, tools):
        ctx = last_user(messages)
        assert "CONTEXT" in ctx
        return json.dumps({"action": "final", "answer": "The Plus plan costs 45 EUR per month.",
                           "citations": [{"chunk_id": "C1", "quote": "The Plus plan costs 45 EUR per month"}],
                           "refused": False, "confidence": 0.9})

    hub = make_fake_hub(agent=model)
    rt = AgentRuntime.load(agent_dir / "agent.yaml", cfg=cfg, llm=hub.agent)
    # make C1 the right chunk regardless of ranking by citing via quote search
    ans, trace = rt.answer("How much is the Plus plan?")
    assert "45 EUR" in ans.answer
    assert trace["hits"]
    # the citation is kept only if the quote is really in the cited passage
    for c in ans.citations:
        assert c.doc_id == "membership_rules"


def test_tool_protocol(agent_dir, cfg, make_fake_hub):
    replies = iter([
        json.dumps({"action": "call_tool", "tool": "calculator", "args": {"expression": "45 * 12"}}),
        json.dumps({"action": "final", "answer": "A year of Plus costs 540 EUR.", "citations": [], "refused": False}),
    ])
    hub = make_fake_hub(agent=lambda m, t: next(replies))
    rt = AgentRuntime.load(agent_dir / "agent.yaml", cfg=cfg, llm=hub.agent)
    ans, trace = rt.answer("What does a year of Plus cost?")
    assert ans.tool_calls and ans.tool_calls[0].result["result"] == 540
    assert "540" in ans.answer


def test_fabricated_quote_is_dropped(agent_dir, cfg, make_fake_hub):
    hub = make_fake_hub(agent=lambda m, t: json.dumps({
        "action": "final", "answer": "Guests are free every day.",
        "citations": [{"chunk_id": "C1", "quote": "Guests are always free on every single day of the year"}]}))
    rt = AgentRuntime.load(agent_dir / "agent.yaml", cfg=cfg, llm=hub.agent)
    ans, trace = rt.answer("Can I bring guests?")
    assert not ans.citations and trace["invalid_citations"]


def test_deterministic_refusal_without_llm(agent_dir, cfg, make_fake_hub):
    agent = load_agent(agent_dir / "agent.yaml")
    agent = agent.model_copy(update={"tools": [], "retrieval": agent.retrieval.model_copy(update={"min_score": 0.99})})
    calls = []
    hub = make_fake_hub(agent=lambda m, t: calls.append(1) or "{}")
    rt = AgentRuntime.load(agent, agent_dir=agent_dir, cfg=cfg, llm=hub.agent)
    ans, trace = rt.answer("What is the capital of Peru?")
    assert ans.refused and trace["deterministic_refusal"] and not calls


def test_unknown_tool_in_yaml(agent_dir, cfg, make_fake_hub):
    agent = load_agent(agent_dir / "agent.yaml")
    bad = agent.model_copy(update={"tools": [ToolBinding.model_construct(name="teleport", reason="", config={})]})
    with pytest.raises(ValueError):
        AgentRuntime.load(bad, agent_dir=agent_dir, cfg=cfg, llm=make_fake_hub().agent)
