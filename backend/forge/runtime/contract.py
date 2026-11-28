"""Enforce the output contract on every answer: parse, map citations, verify quotes, trim."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from forge.llm.repair import extract_json
from forge.schemas.agent_def import OutputContract
from forge.schemas.answer import AgentAnswer, Citation, ModelAnswer, ToolCallRecord
from forge.schemas.corpus import Chunk
from forge.util import find_span, quote_in_text

_LABEL = re.compile(r"^\[?C(\d+)\]?$", re.IGNORECASE)


def _resolve_chunk(ref: str | None, labels: dict[str, Chunk], by_id: dict[str, Chunk]) -> Chunk | None:
    if not ref:
        return None
    ref = str(ref).strip()
    m = _LABEL.match(ref)
    if m:
        return labels.get(f"C{m.group(1)}")
    return by_id.get(ref)


def enforce(raw: str | dict | None, hits_chunks: list[Chunk], tool_calls: list[ToolCallRecord],
            contract: OutputContract, refusal_message: str) -> tuple[AgentAnswer, dict[str, Any]]:
    """Return (answer, trace_extras). trace_extras keeps what was dropped so the judge can penalise it."""
    labels = {f"C{i + 1}": c for i, c in enumerate(hits_chunks)}
    by_id = {c.chunk_id: c for c in hits_chunks}
    extras: dict[str, Any] = {"schema_valid": True, "invalid_citations": [], "repaired_quotes": 0}

    data = raw if isinstance(raw, dict) else extract_json(raw or "")
    if not isinstance(data, dict):
        extras["schema_valid"] = False
        text = (raw if isinstance(raw, str) else "") or ""
        return AgentAnswer(answer=text.strip()[:2000], tool_calls=tool_calls, confidence=0.0), extras
    data = {k: v for k, v in data.items() if k != "action"}
    if not data.get("answer"):  # models sometimes rename the field
        for alt in ("final_answer", "response", "text", "content"):
            if isinstance(data.get(alt), str) and data[alt].strip():
                data["answer"] = data[alt]
                break
    try:
        model_ans = ModelAnswer.model_validate({**data, "citations": []})
    except ValidationError:
        extras["schema_valid"] = False
        model_ans = ModelAnswer(answer=str(data.get("answer", ""))[:2000])

    citations: list[Citation] = []
    for c in data.get("citations") or []:
        if isinstance(c, str):
            c = {"chunk_id": c, "quote": ""}
        if not isinstance(c, dict):
            continue
        chunk = _resolve_chunk(c.get("chunk_id") or c.get("id") or c.get("source"), labels, by_id)
        quote = str(c.get("quote") or "").strip()
        if chunk is None:
            # maybe the quote identifies the chunk
            chunk = next((h for h in hits_chunks if quote and quote_in_text(quote, h.text)), None)
        if chunk is None:
            extras["invalid_citations"].append({"ref": c, "reason": "unknown passage"})
            continue
        if quote and not quote_in_text(quote, chunk.text):
            extras["invalid_citations"].append({"ref": c, "chunk_id": chunk.chunk_id, "reason": "quote not in passage"})
            continue
        if quote:
            exact = find_span(quote, chunk.text)
            if exact and exact != quote:
                extras["repaired_quotes"] += 1
                quote = exact
        else:
            quote = chunk.text.strip()[:160]
        citations.append(Citation(doc_id=chunk.doc_id, page=chunk.page, chunk_id=chunk.chunk_id, quote=quote))

    answer_text = model_ans.answer.strip()
    words = answer_text.split()
    if len(words) > contract.max_words:
        answer_text = " ".join(words[:contract.max_words]) + " ..."
        extras["trimmed"] = True
    if model_ans.refused and not answer_text:
        answer_text = refusal_message
    if not answer_text and not model_ans.refused and not model_ans.clarifying_question:
        # never show the user an empty reply (for example after the model kept asking for tools)
        answer_text = "Sorry, I could not put together an answer to that. Please try rephrasing the question."
        extras["empty_answer"] = True
        model_ans.confidence = 0.0

    confidence = model_ans.confidence
    if contract.require_citations and not model_ans.refused and not citations and \
            not any(t.error is None for t in tool_calls) and not model_ans.clarifying_question:
        confidence = min(confidence, 0.2)
        extras["uncited"] = True

    ans = AgentAnswer(answer=answer_text, citations=citations, tool_calls=tool_calls, refused=model_ans.refused,
                      refusal_reason=model_ans.refusal_reason, clarifying_question=model_ans.clarifying_question,
                      confidence=max(0.0, min(1.0, confidence)))
    return ans, extras


def render_for_chat(ans: AgentAnswer) -> str:
    lines = [ans.answer]
    if ans.clarifying_question and ans.clarifying_question not in ans.answer:
        lines.append(f"\n{ans.clarifying_question}")
    if ans.tool_calls:
        lines.append("\nTools used: " + ", ".join(f"{t.tool}({t.arguments})" for t in ans.tool_calls))
    if ans.citations:
        lines.append("\nSources:")
        for i, c in enumerate(ans.citations, start=1):
            page = f" p.{c.page}" if c.page else ""
            lines.append(f"  [{i}] {c.doc_id}{page}: \"{c.quote[:160]}\"")
    return "\n".join(lines)
