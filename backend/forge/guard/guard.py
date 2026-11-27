"""Stage "guard" (Req 2): flag asks the documents can't support. Never silently expands the brief."""

from __future__ import annotations

import re

from forge.context import RunContext
from forge.guard.asks import extract_asks
from forge.guard.probes import make_probes, tool_signals
from forge.guard.verifier import aggregate, verify
from forge.intake.interviewer import save_requirements
from forge.schemas.corpus import Chunk, CorpusProfile
from forge.schemas.groundability import GroundabilityReport
from forge.schemas.requirements import MustRefuse, Requirements
from forge.util import read_jsonl, read_model, slugify, write_json


MAX_ASKS = 12
_GENERIC = {"information", "provide", "answer", "questions", "tell", "about", "what", "how", "users", "available",
            "does", "handled"}
_LIVE = re.compile(r"\b(live|real[- ]time|today'?s?|current|right now)\b", re.I)


def mentioned_in_corpus(ask: str, vocabulary: set[str]) -> bool:
    """True when nearly all of the ask's meaningful words occur in the documents: a deterministic second
    opinion on an 'unsupported' verdict from a small model. Live-data asks are never rescued."""
    from forge.evals.validator import content_words  # local import: validator imports this package


    words = {w[:6] for w in content_words(ask) if w not in _GENERIC}
    if len(words) < 2 or _LIVE.search(ask):
        return False
    return len(words & {w[:6] for w in vocabulary}) / len(words) >= 0.75


def run_guard(ctx: RunContext) -> GroundabilityReport:
    req = read_model(ctx.path("requirements.json"), Requirements)
    profile = read_model(ctx.path("corpus_profile.json"), CorpusProfile)
    retriever = ctx.retriever()
    llm = ctx.hub.builder

    chunks = read_jsonl(ctx.path("corpus", "chunks.jsonl"), Chunk)
    table_words = " ".join(f"{t.name} {' '.join(c.name for c in t.columns)}" for t in profile.tables)
    from forge.evals.validator import content_words


    vocabulary = content_words(" ".join(c.text for c in chunks) + " " + table_words.replace("_", " "))

    verdicts = []
    asks = extract_asks(ctx.brief, req, llm)
    if len(asks) > MAX_ASKS:  # cost control: each ask costs about two probe checks
        ctx.note(f"guard: checked the first {MAX_ASKS} of {len(asks)} asks (must-answer topics first)")
    for ask, source in asks[:MAX_ASKS]:
        probes = []
        for q in make_probes(ask, llm):
            probes.append(verify(q, retriever.search(q, k=5), llm))
        verdict = aggregate(ask.id, ask.text, source, probes, tool_signals(ask.text, profile))
        if verdict.verdict == "unsupported" and mentioned_in_corpus(ask.text, vocabulary):
            verdict.verdict = "partial"
            verdict.explanation += ("; the documents or table columns use these terms, so the agent is not told to "
                                    "refuse it (it still refuses at answer time if the passages lack the answer)")
        verdicts.append(verdict)

    warnings, moved = [], []
    existing = {m.topic.lower() for m in req.must_refuse}
    keep_answer = []
    unsupported_ids = {v.ask_id for v in verdicts if v.verdict == "unsupported"}
    for v in verdicts:
        if v.verdict == "unsupported":
            warnings.append(f"Not supported by the documents: '{v.ask_text}'. The agent will refuse it.")
            if v.ask_text.lower() not in existing:
                req.must_refuse.append(MustRefuse(id=f"rg_{slugify(v.ask_id + '_' + v.ask_text, 24)}",
                                                  topic=v.ask_text, source="guard",
                                                  reason="the documents do not contain this information"))
                moved.append(v.ask_id)
        elif v.verdict == "partial":
            warnings.append(f"Only partly supported: '{v.ask_text}'. Answers may be incomplete.")
        elif v.verdict == "needs_tool":
            warnings.append(f"'{v.ask_text}' needs the {v.needed_tool} tool rather than the documents.")
    for m in req.must_answer:
        if m.id not in unsupported_ids:
            keep_answer.append(m)
    req.must_answer = keep_answer or req.must_answer
    report = GroundabilityReport(verdicts=verdicts, moved_to_refuse=moved, warnings=warnings,
                                 coverage=round(sum(1.0 if v.verdict in ("supported", "needs_tool") else
                                                    0.5 if v.verdict == "partial" else 0.0 for v in verdicts)
                                                / max(1, len(verdicts)), 3))
    write_json(ctx.path("groundability.json"), report)
    save_requirements(ctx, req)
    ctx.emit("guard", "info", f"{len(verdicts)} asks checked, coverage {report.coverage:.0%}, "
                              f"{len(moved)} moved to must-refuse")
    return report
