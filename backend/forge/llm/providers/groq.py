"""Hosted open-weight models on Groq's free tier. Used on Render, which has no GPU.

Note for the report: the assignment asks for a local small open model as judge. Locally the judge runs on
Ollama; on Render the same open-weight families run hosted on Groq. REPORT.md states which provider ran.
Model ids live in .env (AGENT_MODEL / JUDGE_MODEL), never in code.
"""

from __future__ import annotations

from forge.llm.providers.openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"
