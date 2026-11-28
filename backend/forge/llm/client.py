"""The high-level LLM call used by every stage.

complete():  render prompt -> cache lookup -> budget -> provider -> parse/validate -> repair (max 2) -> log.
On final failure it returns LLMResult(ok=False, degraded=True) so the CALLER uses its deterministic fallback.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from forge.config import ForgeConfig
from forge.errors import BudgetExceeded, ProviderError
from forge.llm.budget import Budget
from forge.llm.cache import LLMCache, NullCache
from forge.llm.prompts import render
from forge.llm.providers import BaseProvider, RawResponse, make_provider
from forge.llm.repair import coerce, extract_json, schema_hint

Role = Literal["agent", "judge", "builder"]
LOCAL_PROVIDERS = {"ollama", "fake"}  # providers that cost nothing, allowed to run in cache-only mode


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    data: Any = None
    degraded: bool = False
    repairs: int = 0
    cached: bool = False
    error: str | None = None


@dataclass
class ChatResult:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    latency_ms: int = 0
    cached: bool = False


class LLMClient:
    def __init__(self, provider: BaseProvider, budget: Budget, cache: LLMCache | NullCache, role: Role,
                 seed: int = 7, cache_only: bool = False):
        self.provider = provider
        self.cache_only = cache_only
        self.budget = budget
        self.cache = cache
        self.role = role
        self.seed = seed
        self.log_path: Path | None = None
        self.used_prompts: set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ public
    @property
    def model_id(self) -> str:
        return f"{self.provider.name}:{self.provider.model}"

    def set_log(self, path: Path | None) -> None:
        self.log_path = path

    def complete(self, prompt_id: str, variables: dict[str, Any] | None = None, *,
                 schema: type[BaseModel] | None = None, system: str | None = None,
                 temperature: float = 0.0, max_tokens: int = 1500) -> LLMResult:
        prompt = render(prompt_id, **(variables or {}))
        self.used_prompts.add(prompt_id)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.complete_messages(messages, schema=schema, prompt_id=prompt_id, temperature=temperature,
                                      max_tokens=max_tokens)

    def complete_messages(self, messages: list[dict[str, Any]], *, schema: type[BaseModel] | None = None,
                          prompt_id: str = "adhoc", temperature: float = 0.0, max_tokens: int = 1500) -> LLMResult:
        msgs = list(messages)
        if schema is not None:
            msgs.append({"role": "system", "content": "Reply with ONLY a JSON object that matches this JSON schema "
                                                       f"(no prose, no code fences): {schema_hint(schema)}"})
        try:
            raw, cached = self._call(msgs, schema, None, temperature, max_tokens)
        except ProviderError as exc:
            self._log(prompt_id, ok=False, error=str(exc))
            return LLMResult(ok=False, degraded=True, error=str(exc))
        if schema is None:
            self._log(prompt_id, ok=True, raw=raw, cached=cached)
            return LLMResult(ok=True, text=raw.text, cached=cached)

        data, err = self._parse(raw.text, schema)
        repairs = 0
        while data is None and repairs < 2:
            repairs += 1
            fix_msgs = msgs + [
                {"role": "assistant", "content": raw.text[:6000]},
                {"role": "user", "content": render("repair_json", error=err or "invalid JSON",
                                                   schema=schema_hint(schema))},
            ]
            try:
                raw, _ = self._call(fix_msgs, schema, None, 0.0, max_tokens)
            except ProviderError as exc:
                err = str(exc)
                break
            data, err = self._parse(raw.text, schema)
        ok = data is not None
        self._log(prompt_id, ok=ok, raw=raw, cached=cached, repairs=repairs, error=None if ok else err)
        return LLMResult(ok=ok, text=raw.text, data=data, degraded=not ok, repairs=repairs, cached=cached,
                         error=None if ok else err)

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None, *,
             temperature: float = 0.0, max_tokens: int = 1200, json_mode: bool = False) -> ChatResult:
        """Free-form chat (used by the agent runtime). Raises ProviderError on failure."""
        schema = {"type": "object"} if json_mode else None
        raw, cached = self._call(messages, None, tools, temperature, max_tokens, json_schema_override=schema)
        self._log("runtime_chat", ok=True, raw=raw, cached=cached)
        return ChatResult(text=raw.text, tool_calls=raw.tool_calls, tokens=raw.tokens_in + raw.tokens_out,
                          latency_ms=raw.latency_ms, cached=cached)

    def health(self) -> tuple[bool, str]:
        return self.provider.health()

    # ----------------------------------------------------------------- private
    def _call(self, messages, schema, tools, temperature, max_tokens, json_schema_override=None):
        json_schema = json_schema_override
        if schema is not None and self.provider.supports_json_schema:
            json_schema = schema.model_json_schema()
        elif schema is not None:
            json_schema = {"type": "object"}
        key = hashlib.sha256(json.dumps(
            [self.provider.name, self.provider.model, messages, json_schema, tools, temperature, self.seed,
             max_tokens], sort_keys=True, default=str).encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is not None:
            d = json.loads(hit)
            self.budget.cached_calls += 1
            return RawResponse(text=d["text"], tool_calls=d.get("tool_calls", [])), True
        if self.cache_only and self.provider.name not in LOCAL_PROVIDERS:
            raise ProviderError(f"cache-only mode: no cached reply for this {self.provider.name} call, "
                                "and hosted calls are switched off (FORGE_CACHE_ONLY=1)")
        self.budget.charge_call()
        raw = self.provider.generate(messages, json_schema=json_schema, tools=tools, temperature=temperature,
                                     seed=self.seed, max_tokens=max_tokens)
        self.budget.add_tokens(raw.tokens_in + raw.tokens_out)
        self.cache.put(key, json.dumps({"text": raw.text, "tool_calls": raw.tool_calls}))
        return raw, False

    @staticmethod
    def _parse(text: str, schema: type[BaseModel]) -> tuple[BaseModel | None, str | None]:
        obj = extract_json(text)
        if obj is None:
            return None, "output was not valid JSON"
        try:
            return schema.model_validate(coerce(schema, obj)), None
        except ValidationError as exc:
            return None, str(exc)[:1500]

    def _log(self, prompt_id: str, ok: bool, raw: RawResponse | None = None, cached: bool = False,
             repairs: int = 0, error: str | None = None) -> None:
        if self.log_path is None:
            return
        rec = {"ts": round(time.time(), 3), "role": self.role, "prompt_id": prompt_id, "model": self.model_id,
               "ok": ok, "cached": cached, "repairs": repairs, "error": error,
               "tokens_in": raw.tokens_in if raw else 0, "tokens_out": raw.tokens_out if raw else 0,
               "latency_ms": raw.latency_ms if raw else 0}
        with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")


@dataclass
class LLMHub:
    """The three clients of a run, sharing one budget and one cache."""
    agent: LLMClient
    judge: LLMClient
    builder: LLMClient
    budget: Budget

    def set_log(self, path: Path | None) -> None:
        for c in (self.agent, self.judge, self.builder):
            c.set_log(path)

    @property
    def used_prompts(self) -> set[str]:
        return self.agent.used_prompts | self.judge.used_prompts | self.builder.used_prompts


def _family(model: str) -> str:
    m = model.lower().split("/")[-1]
    for fam in ("qwen", "llama", "gemma", "mistral", "mixtral", "phi", "deepseek", "granite", "olmo"):
        if fam in m:
            return fam
    return m.split(":")[0].split("-")[0]


def make_hub(cfg: ForgeConfig, budget: Budget | None = None, providers: dict[str, BaseProvider] | None = None) -> LLMHub:
    """Build agent/judge/builder clients. `providers` lets tests inject fakes."""
    llm = cfg.llm
    budget = budget or Budget(cfg.budget, llm.requests_per_minute)
    cache: LLMCache | NullCache = LLMCache(llm.cache_path) if llm.use_cache else NullCache()
    providers = providers or {}
    agent_p = providers.get("agent") or make_provider(llm.agent_provider, llm.agent_model, llm)
    judge_p = providers.get("judge") or make_provider(llm.judge_provider, llm.judge_model, llm)
    if "judge" not in providers and llm.judge_provider == "ollama" and llm.agent_provider != "ollama":
        ok, msg = judge_p.health()
        if not ok:  # never fail a run because the local judge is missing: fall back, loudly
            import logging

            logging.getLogger("forgeai").warning(
                "local judge unavailable (%s); falling back to the agent's provider %s:%s. Install Ollama and "
                "`ollama pull %s` to use a local judge.", msg, llm.agent_provider, llm.agent_model, llm.judge_model)
            judge_p = make_provider(llm.agent_provider, llm.agent_model, llm)
            judge_p.fallback_reason = msg  # type: ignore[attr-defined]
    builder_p = providers.get("builder") or agent_p
    seed = cfg.judge.seed
    co = llm.cache_only
    return LLMHub(agent=LLMClient(agent_p, budget, cache, "agent", seed, co),
                  judge=LLMClient(judge_p, budget, cache, "judge", seed, co),
                  builder=LLMClient(builder_p, budget, cache, "builder", seed, co), budget=budget)


def same_family(cfg: ForgeConfig) -> bool:
    return _family(cfg.llm.agent_model) == _family(cfg.llm.judge_model)


__all__ = ["LLMClient", "LLMHub", "LLMResult", "ChatResult", "make_hub", "same_family", "BudgetExceeded"]
