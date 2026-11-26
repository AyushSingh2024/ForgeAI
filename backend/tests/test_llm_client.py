"""The structured-output safety net: extraction, repair, fallback, cache, budget, provider switch."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from forge.config import load_config, with_overrides
from forge.errors import BudgetExceeded
from forge.llm.client import make_hub, same_family
from forge.llm.repair import extract_json
from tests.conftest import FakeProvider


class Item(BaseModel):
    name: str
    qty: int


def test_extract_json_handles_fences_and_chatter():
    assert extract_json('Sure! ```json\n{"a": 1,}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": [1, 2]} hope it helps') == {"a": [1, 2]}
    assert extract_json("no json here") is None


def test_repair_then_valid(make_fake_hub):
    replies = iter(['{"name": "bolt"}', '{"name": "bolt", "qty": 3}'])
    hub = make_fake_hub(agent=lambda m, t: next(replies))
    res = hub.agent.complete_messages([{"role": "user", "content": "x"}], schema=Item)
    assert res.ok and res.data.qty == 3 and res.repairs == 1


def test_degraded_after_two_repairs(make_fake_hub):
    hub = make_fake_hub(agent=lambda m, t: "not json")
    res = hub.agent.complete_messages([{"role": "user", "content": "x"}], schema=Item)
    assert not res.ok and res.degraded and res.repairs == 2


def test_cache_hit(tmp_path):
    cfg = with_overrides(load_config(env={}), "llm", use_cache=True, cache_path=str(tmp_path / "c.sqlite"))
    p = FakeProvider(lambda m, t: '{"name": "a", "qty": 1}')
    hub = make_hub(cfg, providers={"agent": p, "judge": p})
    msgs = [{"role": "user", "content": "same"}]
    hub.agent.complete_messages(msgs, schema=Item)
    second = hub.agent.complete_messages(msgs, schema=Item)
    assert second.cached and len(p.calls) == 1


def test_budget_exceeded(cfg):
    cfg = with_overrides(cfg, "budget", max_llm_calls=1)
    p = FakeProvider(lambda m, t: "hi")
    hub = make_hub(cfg, providers={"agent": p, "judge": p})
    hub.agent.complete_messages([{"role": "user", "content": "1"}])
    with pytest.raises(BudgetExceeded):
        hub.agent.complete_messages([{"role": "user", "content": "2"}])


def test_provider_switch_and_family_check():
    cfg = load_config(env={"LLM_PROVIDER": "groq", "GROQ_API_KEY": "k", "AGENT_MODEL": "llama-3.1-8b-instant",
                           "JUDGE_PROVIDER": "groq", "JUDGE_MODEL": "gemma2-9b-it"})
    hub = make_hub(cfg)
    assert hub.agent.provider.name == "groq"
    assert not same_family(cfg)
    assert same_family(load_config(env={"AGENT_MODEL": "qwen2.5:7b", "JUDGE_MODEL": "qwen2.5:14b"}))
