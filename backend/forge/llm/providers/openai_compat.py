"""Shared adapter for OpenAI-compatible chat completion APIs (Groq, Hugging Face Inference)."""

from __future__ import annotations

import json
from typing import Any

from forge.llm.providers.base import BaseProvider, RawResponse


class OpenAICompatProvider(BaseProvider):
    name = "openai_compat"
    supports_json_schema = False
    supports_tools = True
    base_url = ""

    def __init__(self, model: str, api_key: str, timeout_s: float = 120.0):
        super().__init__(model, timeout_s)
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _generate(self, messages, *, json_schema, tools, temperature, seed, max_tokens) -> RawResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "seed": seed,
        }
        if json_schema is not None and not tools:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools
        data = self._post(f"{self.base_url}/chat/completions", payload, self._headers())
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": fn.get("name", ""), "arguments": args})
        usage = data.get("usage", {}) or {}
        return RawResponse(text=msg.get("content") or "", tool_calls=calls,
                           tokens_in=int(usage.get("prompt_tokens", 0) or 0),
                           tokens_out=int(usage.get("completion_tokens", 0) or 0), raw=data)

    def health(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, f"{self.name}: API key is not set"
        try:
            self.generate([{"role": "user", "content": "ping"}], max_tokens=1)
        except Exception as exc:  # noqa: BLE001
            return False, f"{self.name}: {exc}"
        return True, "ok"
