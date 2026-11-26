"""Hugging Face Inference Providers (OpenAI-compatible router) as a second hosted fallback."""

from __future__ import annotations

from forge.llm.providers.openai_compat import OpenAICompatProvider


class HFProvider(OpenAICompatProvider):
    name = "hf"
    base_url = "https://router.huggingface.co/v1"
    supports_tools = False
