"""LLM provider adapters behind one interface. Pick one with make_provider(name, model, cfg)."""

from __future__ import annotations

from forge.config import LLMCfg
from forge.llm.providers.base import BaseProvider, RawResponse
from forge.llm.providers.groq import GroqProvider
from forge.llm.providers.hf import HFProvider
from forge.llm.providers.ollama import OllamaProvider
from forge.llm.providers.openai import OpenAIProvider

__all__ = ["BaseProvider", "RawResponse", "make_provider"]


def make_provider(name: str, model: str, cfg: LLMCfg) -> BaseProvider:
    name = name.lower()
    if name == "ollama":
        return OllamaProvider(model, cfg.ollama_base_url, cfg.timeout_s)
    if name == "groq":
        return GroqProvider(model, cfg.groq_api_key, cfg.timeout_s)
    if name == "hf":
        return HFProvider(model, cfg.hf_api_token, cfg.timeout_s)
    if name == "openai":
        return OpenAIProvider(model, cfg.openai_api_key, cfg.timeout_s)
    raise ValueError(f"unknown LLM provider '{name}' (use ollama, groq, hf or openai)")
