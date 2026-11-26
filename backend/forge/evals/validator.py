"""Reject bad generated cases BEFORE they are used to grade anything."""

from __future__ import annotations

import re

import numpy as np

from forge.guard.verifier import verify
from forge.llm.client import LLMClient
from forge.retrieval.embedder import Embedder
from forge.retrieval.hybrid import HybridRetriever
from forge.schemas.corpus import Chunk
from forge.schemas.eval_case import EvalCase, FactCheck, KeyFact
from forge.util import find_span, normalize, number_in, parse_numbers, quote_in_text

_STOP = set("the a an of to in on for and or is are be by with at as it this that from can may must will "
            "you your per each any all not no".split())


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", normalize(text)) if w not in _STOP and len(w) > 2}


def fact_supported_cheap(fact: KeyFact, text: str) -> bool | None:
    """True/False when decidable without an LLM, None when an entailment check is needed."""
    nums = parse_numbers(fact.fact)
    if nums:
        src = parse_numbers(text)
        return all(number_in(n, src) for n in nums)
    words = content_words(fact.fact)
    if not words:
        return None
    overlap = len(words & content_words(text)) / len(words)
    if overlap >= 0.6:
        return True
    return None


class Validator:
    def __init__(self, chunks_by_id: dict[str, Chunk], retriever: HybridRetriever, embedder: Embedder,
                 llm: LLMClient, dedupe_similarity: float = 0.9):
        self.chunks = chunks_by_id
        self.retriever = retriever
        self.embedder = embedder
        self.llm = llm
        self.dedupe = dedupe_similarity
        self._accepted_vecs: list[np.ndarray] = []

    def _entailed(self, fact: str, text: str) -> bool:
        res = self.llm.complete("eval_fact_check", {"text": text[:2500], "fact": fact}, schema=FactCheck, max_tokens=200)
        return bool(res.ok and res.data.entailed)

    def validate(self, case: EvalCase) -> tuple[bool, EvalCase, str]:
        repairs: list[str] = []
        c = case.model_copy(deep=True)

        if c.category in ("answerable", "multi_doc", "ambiguous", "edge") and c.expected_behavior != "refuse":
            if not c.sources:
                return False, c, "no_source"
            for s in c.sources:
                chunk = self.chunks.get(s.chunk_id)
                if chunk is None:
                    return False, c, "unknown_chunk"
                if not quote_in_text(s.quote, chunk.text, fuzzy_threshold=101):
                    span = find_span(s.quote, chunk.text, threshold=90)
                    if not span:
                        return False, c, "quote_not_in_source"
                    s.quote = span
                    repairs.append("quote repaired by fuzzy match")
            if c.category == "multi_doc" and len({s.doc_id for s in c.sources}) < 2:
                return False, c, "multi_doc_needs_two_documents"
            source_text = "\n".join(self.chunks[s.chunk_id].text for s in c.sources)
            kept = []
            for f in c.key_facts:
                ok = fact_supported_cheap(f, source_text)
                if ok is None:
                    ok = self._entailed(f.fact, source_text)
                if ok:
                    if parse_numbers(f.fact) and f.kind != "numeric":
                        f.kind = "numeric"
                    kept.append(f)
                else:
                    repairs.append(f"dropped unsupported fact: {f.fact[:60]}")
            if c.expected_behavior == "answer" and not kept:
                return False, c, "no_supported_key_facts"
            c.key_facts = kept
            if c.expected_behavior == "answer" and c.category != "edge":
                q = normalize(c.question)
                if any(len(normalize(s.quote)) > 30 and normalize(s.quote) in q for s in c.sources):
                    return False, c, "question_contains_answer"

        if c.expected_behavior == "refuse" and c.category in ("must_refuse", "edge") and \
                "ignore" not in c.question.lower():
            hits = self.retriever.search(c.question, k=5)
            probe = verify(c.question, hits, self.llm)
            if probe.quote_verified:
                return False, c, "refuse_case_is_answerable"

        vec = self.embedder.embed_query(c.question)
        for v in self._accepted_vecs:
            if float(v @ vec) > self.dedupe:
                return False, c, "duplicate"
        self._accepted_vecs.append(vec)
        c.generation.validated = True
        c.generation.repairs = repairs
        return True, c, ""
