"""Req 6: failure classification rules and targeted (one-knob) fixers."""

from __future__ import annotations

from forge.optimizer.classifier import classify, group
from forge.optimizer.fixers import fix_hallucination, fix_retrieval_miss, fix_tool_error
from forge.schemas.agent_def import AgentDefinition, ToolBinding, diff
from forge.schemas.eval_case import EvalCase, KeyFact
from forge.schemas.scorecard import CaseResult, DeterministicResult, JudgeResult


def _res(case_id="a1", gold=None, **det):
    return CaseResult(case_id=case_id, category="answerable", split="train", verdict="fail",
                      deterministic=DeterministicResult(**det), judge=JudgeResult(), gold_in_topk=gold)


ANS = EvalCase(id="a1", category="answerable", question="What is the fee?", key_facts=[KeyFact(fact="25 EUR")])


def test_classifier_rules():
    refuse = EvalCase(id="r1", category="must_refuse", question="medical advice?")
    assert classify(refuse, _res("r1", refusal_correct=False), {})[0] == "false_compliance"
    assert classify(ANS, _res(citation_quote_verbatim=False), {})[0] == "hallucination"
    assert classify(ANS, _res(gold=False, key_fact_coverage=0.0), {})[0] == "retrieval_miss"
    assert classify(ANS, _res(gold=True, key_fact_coverage=0.5), {})[0] == "prompt_defect"
    assert classify(ANS, _res(gold=True, refusal_correct=False), {"answer": {"refused": True}})[0] == "wrong_refusal"


def test_group_orders_by_size():
    rs = [_res("a"), _res("b"), _res("c")]
    rs[0].failure_class = rs[1].failure_class = "prompt_defect"
    rs[2].failure_class = "retrieval_miss"
    assert list(group(rs)) == ["prompt_defect", "retrieval_miss"]


def test_fixers_change_one_knob_and_bump_version(make_fake_hub):
    agent = AgentDefinition()
    tried: set[str] = set()
    cand, _, key = fix_retrieval_miss(agent, [{"case": ANS, "transcript": {}}], tried, make_fake_hub().builder)
    changed = {d["path"] for d in diff(agent, cand)}
    assert changed == {"retrieval.top_k"} and cand.version == agent.version + 1
    tried.add(key)
    cand2, _, _ = fix_retrieval_miss(agent, [{"case": ANS, "transcript": {}}], tried, make_fake_hub().builder)
    assert {d["path"] for d in diff(agent, cand2)} != changed  # the next option, not a repeat

    h, _, _ = fix_hallucination(agent, [], set(), make_fake_hub().builder)
    assert {d["path"] for d in diff(agent, h)} <= {"system_prompt.slots.grounding", "system_prompt.slots.citation_rule"}

    with_tools = agent.model_copy(update={"tools": [ToolBinding(name="calculator", reason="maths")]})
    t, _, _ = fix_tool_error(with_tools, [], set(), make_fake_hub().builder)
    assert "calculator" in t.system_prompt.slots.tool_rules
