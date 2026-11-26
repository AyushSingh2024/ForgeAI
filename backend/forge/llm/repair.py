"""Helpers that make small models produce valid structured output."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _balanced_block(text: str) -> str | None:
    """Return the first balanced {...} or [...] block, respecting strings."""
    start = None
    stack: list[str] = []
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if start is None:
            if ch in "{[":
                start = i
                stack.append("}" if ch == "{" else "]")
            continue
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack or stack[-1] != ch:
                return None
            stack.pop()
            if not stack:
                return text[start:i + 1]
    return None


def extract_json(text: str) -> Any | None:
    """Deterministically pull a JSON value out of model output. Returns None if impossible."""
    if not text:
        return None
    candidates = [text.strip()]
    candidates += [m.strip() for m in _FENCE.findall(text)]
    block = _balanced_block(text)
    if block:
        candidates.append(block)
    for cand in candidates:
        for variant in (cand, _TRAILING_COMMA.sub(r"\1", cand)):
            try:
                return json.loads(variant)
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def coerce(model_cls: type[BaseModel], data: Any) -> Any:
    """Light fixes before validation: unwrap {"items": [...]}-style wrappers and single-key envelopes."""
    if isinstance(data, dict) and len(data) == 1:
        (key, value), = data.items()
        fields = set(model_cls.model_fields)
        if key not in fields and isinstance(value, (dict, list)):
            if isinstance(value, dict):
                return value
            if len(fields) == 1:
                return {next(iter(fields)): value}
    if isinstance(data, list):
        fields = list(model_cls.model_fields)
        if len(fields) == 1:
            return {fields[0]: data}
    return data


def schema_hint(model_cls: type[BaseModel]) -> str:
    """Compact JSON schema text appended to prompts (helps providers without native schema support)."""
    return json.dumps(model_cls.model_json_schema(), separators=(",", ":"))
