"""The ONLY place that talks to a language model. Everything else calls LLMClient / LLMHub."""

from forge.llm.client import ChatResult, LLMClient, LLMHub, LLMResult, make_hub, same_family

__all__ = ["ChatResult", "LLMClient", "LLMHub", "LLMResult", "make_hub", "same_family"]
