"""Does the evidence really support the ask? LLM opinion + a deterministic quote check that can overrule it."""

from __future__ import annotations

from forge.llm.client import LLMClient
from forge.retrieval.hybrid import Hit
from forge.schemas.groundability import AskVerdict, Probe, RetrievedRef, VerifyResult
from forge.util import quote_in_text


def verify(probe_q: str, hits: list[Hit], llm: LLMClient) -> Probe:
    probe = Probe(question=probe_q, retrieved=[RetrievedRef(chunk_id=h.chunk_id, score=round(h.score, 5)) for h in hits])
    if not hits:
        return probe
    passages = [{"id": h.chunk_id, "text": h.chunk.text[:1200]} for h in hits[:5]]
    res = llm.complete("guard_verify", {"question": probe_q, "passages": passages}, schema=VerifyResult, max_tokens=500)
    if not res.ok:
        return probe
    v: VerifyResult = res.data
    probe.llm_said_supported = v.supported
    if v.supported and v.quote:
        ordered = sorted(hits, key=lambda h: h.chunk_id != v.chunk_id)  # the passage the model named first
        for h in ordered:
            if quote_in_text(v.quote, h.chunk.text):
                probe.quote_verified = True
                probe.supporting_quote = v.quote
                probe.supporting_chunk_id = h.chunk_id
                break
    return probe


def aggregate(ask_id: str, ask_text: str, source: str, probes: list[Probe], tool_hits: list[str]) -> AskVerdict:
    verified = sum(p.quote_verified for p in probes)
    claimed = sum(p.llm_said_supported for p in probes)
    # probes are written by a model and can be over-specific, so a majority of verified probes counts as support
    if probes and verified * 2 >= len(probes) and verified > 0:
        verdict = "supported"
    elif verified > 0:
        verdict = "partial"
    elif tool_hits:
        verdict = "needs_tool"
    else:
        verdict = "unsupported"
    explanation = f"{verified}/{len(probes)} probes had a verified supporting quote"
    if claimed > verified:
        explanation += f"; the model claimed support {claimed - verified} more time(s) but the quote was not in the passages"
    needed = None
    if verdict == "needs_tool" or (verdict == "partial" and tool_hits):
        needed = tool_hits[0]
    return AskVerdict(ask_id=ask_id, ask_text=ask_text, source=source, verdict=verdict,  # type: ignore[arg-type]
                      needed_tool=needed, probes=probes, explanation=explanation)
