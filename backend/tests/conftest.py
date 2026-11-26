"""Shared pytest fixtures: a scriptable fake LLM provider, a tiny corpus, temp run dirs."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from forge.config import load_config, with_overrides  # noqa: E402
from forge.llm.client import make_hub  # noqa: E402
from forge.llm.providers.base import BaseProvider, RawResponse  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class FakeProvider(BaseProvider):
    """Answers with a user-supplied function(messages, tools) -> str | RawResponse."""

    name = "fake"
    supports_json_schema = True
    supports_tools = True

    def __init__(self, responder: Callable | None = None, model: str = "fake-qwen"):
        super().__init__(model)
        self.responder = responder or (lambda messages, tools: "{}")
        self.calls: list[list[dict]] = []

    def _generate(self, messages, *, json_schema, tools, temperature, seed, max_tokens):
        self.calls.append(messages)
        out = self.responder(messages, tools)
        if isinstance(out, RawResponse):
            return out
        if not isinstance(out, str):
            out = json.dumps(out)
        return RawResponse(text=out, tokens_in=10, tokens_out=10)

    def health(self):
        return True, "ok"


@pytest.fixture
def cfg(tmp_path):
    c = load_config(env={})
    return with_overrides(c, "llm", use_cache=False, cache_path=str(tmp_path / "cache.sqlite"), embedder="hash")


@pytest.fixture
def agent_dir(tmp_path, tiny_corpus) -> Path:
    """A self-contained agent folder: agent.yaml + docs/ (copy of tiny_corpus)."""
    import shutil

    d = tmp_path / "agent"
    shutil.copytree(tiny_corpus, d / "docs")
    shutil.copy(FIXTURES / "handwritten_agent.yaml", d / "agent.yaml")
    return d


@pytest.fixture
def make_fake_hub(cfg):
    def _make(agent=None, judge=None, builder=None):
        agent_p = FakeProvider(agent)
        providers = {"agent": agent_p, "judge": FakeProvider(judge, model="fake-gemma"),
                     "builder": FakeProvider(builder) if builder else agent_p}
        return make_hub(cfg, providers=providers)
    return _make


@pytest.fixture
def tiny_corpus() -> Path:
    return FIXTURES / "tiny_corpus"


@pytest.fixture
def fixed_date(monkeypatch):
    monkeypatch.setenv("FORGE_FIXED_DATE", "2026-01-15")


def scripted(rules: list[tuple[str, object]], default: object = "{}"):
    """Responder that picks a reply by the first substring found in the prompt text.
    A reply may be a value or a callable(messages) -> value."""
    def responder(messages, tools):
        text = "\n".join(str(m.get("content", "")) for m in messages)
        for needle, reply in rules:
            if needle in text:
                return reply(messages) if callable(reply) else reply
        return default
    return responder


@pytest.fixture
def make_run(tmp_path, tiny_corpus, cfg):
    """Create a run folder with input/brief.txt + input/docs and run the ingest stage."""
    import shutil

    from forge.context import RunContext
    from forge.ingest import run_ingest

    def _make(hub, brief="Help gym members with questions about memberships, refunds and classes.", mode="unattended",
              answers=None):
        run_dir = tmp_path / "runs" / "r1"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        shutil.copytree(tiny_corpus, run_dir / "input" / "docs")
        (run_dir / "input" / "brief.txt").write_text(brief, encoding="utf-8")
        ctx = RunContext(run_dir=run_dir, cfg=cfg, hub=hub, mode=mode, answers=answers)
        run_ingest(ctx)
        return ctx
    return _make


def last_user(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return ""
