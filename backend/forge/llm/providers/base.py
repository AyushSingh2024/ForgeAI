"""Provider interface shared by Ollama, Groq and Hugging Face adapters."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from forge.errors import ProviderError


@dataclass
class RawResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    raw: Any = None


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, ProviderError) and exc.retryable


class BaseProvider(ABC):
    name: str = "base"
    supports_json_schema: bool = False
    supports_tools: bool = False

    def __init__(self, model: str, timeout_s: float = 180.0):
        self.model = model
        self.timeout_s = timeout_s
        self._http = httpx.Client(timeout=timeout_s)

    @retry(retry=retry_if_exception(_is_retryable), stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=1, min=2, max=30), reraise=True)
    def generate(self, messages: list[dict[str, Any]], *, json_schema: dict | None = None,
                 tools: list[dict] | None = None, temperature: float = 0.0, seed: int = 7,
                 max_tokens: int = 1024) -> RawResponse:
        start = time.perf_counter()
        resp = self._generate(messages, json_schema=json_schema, tools=tools, temperature=temperature,
                              seed=seed, max_tokens=max_tokens)
        resp.latency_ms = int((time.perf_counter() - start) * 1000)
        return resp

    @abstractmethod
    def _generate(self, messages: list[dict[str, Any]], *, json_schema: dict | None, tools: list[dict] | None,
                  temperature: float, seed: int, max_tokens: int) -> RawResponse: ...

    @abstractmethod
    def health(self) -> tuple[bool, str]: ...

    def _post(self, url: str, payload: dict, headers: dict | None = None) -> dict:
        try:
            r = self._http.post(url, json=payload, headers=headers or {})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderError(f"{self.name}: network error {exc}", retryable=True) from exc
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get("retry-after")
            if retry_after:
                try:
                    time.sleep(min(float(retry_after), 30))
                except ValueError:
                    pass
            raise ProviderError(f"{self.name}: HTTP {r.status_code} {r.text[:200]}", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {r.status_code} {r.text[:300]}", retryable=False)
        return r.json()
