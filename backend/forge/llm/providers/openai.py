"""OpenAI models (testing convenience). The assignment expects small OPEN models, so the official demo runs
should use Ollama (or Groq); REPORT.md shows which provider produced each run."""

from __future__ import annotations

from forge.llm.providers.openai_compat import OpenAICompatProvider


class OpenAIProvider(OpenAICompatProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"
