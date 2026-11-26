"""Local models through Ollama's HTTP API (default, fully offline)."""

from __future__ import annotations

import json
from typing import Any

from forge.llm.providers.base import BaseProvider, RawResponse


class OllamaProvider(BaseProvider):
    name = "ollama"
    supports_json_schema = True
    supports_tools = True

    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout_s: float = 180.0):
        super().__init__(model, timeout_s)
        self.base_url = base_url.rstrip("/")

    def _generate(self, messages, *, json_schema, tools, temperature, seed, max_tokens) -> RawResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "seed": seed, "num_predict": max_tokens},
        }
        if json_schema is not None:
            payload["format"] = json_schema
        if tools:
            payload["tools"] = tools
        data = self._post(f"{self.base_url}/api/chat", payload)
        msg = data.get("message", {}) or {}
        calls = []
        for c in msg.get("tool_calls", []) or []:
            fn = c.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({"name": fn.get("name", ""), "arguments": args})
        return RawResponse(text=msg.get("content", "") or "", tool_calls=calls,
                           tokens_in=int(data.get("prompt_eval_count", 0) or 0),
                           tokens_out=int(data.get("eval_count", 0) or 0), raw=data)

    def health(self) -> tuple[bool, str]:
        try:
            r = self._http.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama not reachable at {self.base_url}: {exc}"
        names = {m.get("name", "") for m in r.json().get("models", [])}
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        if wanted not in names and self.model not in names:
            return False, f"model {self.model} not pulled. Run: ollama pull {self.model}"
        return True, "ok"
