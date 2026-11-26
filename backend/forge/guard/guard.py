"""Stage "guard" (Req 2): flag asks the documents can't support. Never silently expands the brief."""

from __future__ import annotations

from forge.context import RunContext
from forge.guard.asks import extract_asks
from forge.guard.probes import make_probes, tool_signals
from forge.guard.verifier import aggregate, verify
from forge.intake.interviewer import save_requirements
from forge.schemas.corpus import CorpusProfile
from forge.schemas.groundability import GroundabilityReport
from forge.schemas.requirements import MustRefuse, Requirements
from forge.util import read_model, slugify, write_json


def run_guard(ctx: RunContext) -> GroundabilityReport:
    req = read_model(ctx.path("requirements.json"), Requirements)
    profile = read_model(ctx.path("corpus_profile.json"), CorpusProfile)
    retriever = ctx.retriever()
    llm = ctx.hub.builder

    verdicts = []
    for ask, source in extract_asks(ctx.brief, req, llm):
        probes = []
        for q in make_probes(ask, llm):
            probes.append(verify(q, retriever.search(q, k=5), llm))
        verdicts.append(aggregate(ask.id, ask.text, source, probes, tool_signals(ask.text, profile)))

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
