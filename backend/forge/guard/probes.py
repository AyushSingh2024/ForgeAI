"""Probe questions per ask, and rule-based detection of asks that need a tool rather than the documents."""

from __future__ import annotations

import re

from forge.llm.client import LLMClient
from forge.schemas.corpus import CorpusProfile
from forge.schemas.groundability import Ask, ProbeList

TOOL_PATTERNS: dict[str, re.Pattern] = {
    "http_weather": re.compile(r"\b(weather|forecast|wind|rain|temperature|sea state|storm|wave)\b", re.I),
    "current_date": re.compile(r"\b(today|now|current date|this (week|month|year)|days? (until|left|remaining)|"
                               r"still valid|expired?|deadline|how long ago|eta|arrive by)\b", re.I),
    "calculator": re.compile(r"\b(total|sum|calculate|compute|cost of|estimate|how much (would|will)|convert|"
                             r"percentage|percent|average|multiply|times|per diem|balance|difference)\b", re.I),
}


def tool_signals(text: str, profile: CorpusProfile) -> list[str]:
    hits = [name for name, pat in TOOL_PATTERNS.items() if pat.search(text)]
    if profile.tables:
        low = text.lower()
        cols = {c.name.replace("_", " ") for t in profile.tables for c in t.columns}
        names = {t.name.replace("_", " ") for t in profile.tables}
        if any(c in low for c in cols | names if len(c) > 3) or re.search(r"\b(inventory|stock|list|which|how many|"
                                                                          r"in stock|on board|lookup|find)\b", low):
            hits.append("csv_lookup")
    return hits


def make_probes(ask: Ask, llm: LLMClient) -> list[str]:
    res = llm.complete("guard_probe", {"ask": ask.text}, schema=ProbeList, max_tokens=300)
    probes = [p.strip() for p in (res.data.probes if res.ok else []) if p.strip()][:3]
    if not probes:
        probes = [ask.text]
        if ":" in ask.text:
            probes.append(ask.text.split(":", 1)[1].strip())
    return probes
