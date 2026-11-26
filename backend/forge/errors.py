"""Exception types used across the engine."""

from __future__ import annotations

from typing import Any


class ForgeError(Exception):
    """Base class for all ForgeAI errors."""


class BadInput(ForgeError):
    """The brief or the documents cannot be used (empty folder, unreadable files...)."""


class ProviderError(ForgeError):
    """An LLM backend failed."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class BudgetExceeded(ForgeError):
    """The budget guard stopped the run."""


class AwaitingAnswers(ForgeError):
    """The intake interview needs answers from a person (web interactive mode)."""

    def __init__(self, questions: list[dict[str, Any]]):
        super().__init__(f"{len(questions)} interview question(s) waiting for answers")
        self.questions = questions


class Cancelled(ForgeError):
    """A cancel flag was found between stages."""
