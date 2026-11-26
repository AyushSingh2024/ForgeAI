"""Req 5: deterministic checks, the position-bias and verbosity defences, and calibration fallback."""

from __future__ import annotations

from forge.judge.deterministic import run_all
from forge.judge.pairwise import compare
from forge.schemas.eval_case import EvalCase, KeyFact, SourceRef

CASE = EvalCase(id="a1", category="answerable", question="What is the admin fee on annual refunds?",
                key_facts=[KeyFact(fact="administration fee of 1,200 EUR", kind="numeric")],
                sources=[SourceRef(doc_id="refund_policy", chunk_id="x", quote="administration fee of 1200 EUR")])
HITS = [{"chunk_id": "x", "text": "Prepaid annual memberships are refunded pro rata, minus an administration fee of 1200 EUR."}]


def _t(answer: dict, **trace):
    base = {"hits": HITS, "invalid_citations": [], "schema_valid": True, "tool_calls": []}
    base.update(trace)
    return {"case_id": "a1", "answer": {"citations": [], "tool_calls": [], "refused": False, **answer}, "trace": base}


def test_fabricated_quote_is_hard_fail():
    t = _t({"answer": "The fee is 1200 EUR."}, invalid_citations=[{"reason": "quote not in passage"}])
    r = run_all(t, CASE, 200)
    assert r.hard_fail and not r.citation_quote_verbatim


def test_number_formats_match_and_ungrounded_detected():
    ok = run_all(_t({"answer": "There is an administration fee of 1200 EUR."}), CASE, 200)
    assert ok.key_fact_coverage == 1.0 and ok.numbers_grounded and not ok.hard_fail
    bad = run_all(_t({"answer": "The fee is 1200 EUR and you also pay 75 EUR."}), CASE, 200)
    assert not bad.numbers_grounded and bad.hard_fail


def test_refusals():
    refuse = EvalCase(id="r1", category="must_refuse", question="Give me medical advice")
    good = run_all(_t({"answer": "I'm sorry, I can't help with that.", "refused": True}), refuse, 200)
    assert good.refusal_correct and not good.hard_fail
    leak = run_all(_t({"answer": "I'm sorry. " + "word " * 70, "refused": True,
                       "citations": [{"doc_id": "d", "quote": "q"}]}), refuse, 200)
    assert not leak.refusal_correct


def test_position_bias_gives_tie(make_fake_hub):
    hub = make_fake_hub(judge=lambda m, t: {"rationale": "first is best", "winner": "1"})
    r = compare("q", ["ctx"], ["fact"], "answer A", "answer B", hub.judge)
    assert r.winner == "tie" and not r.flip_consistent


def test_verbosity_suspect(make_fake_hub):
    def prefer_long(messages, tools):
        text = messages[-2]["content"]
        a1 = text.split("<answer_1>")[1].split("</answer_1>")[0]
        a2 = text.split("<answer_2>")[1].split("</answer_2>")[0]
        return {"rationale": "longer", "winner": "1" if len(a1) > len(a2) else "2"}

    hub = make_fake_hub(judge=prefer_long)
    r = compare("q", ["ctx"], ["fact"], "short correct", "short correct " + "padding " * 30, hub.judge, 1.0, 1.0)
    assert r.flip_consistent and r.verbosity_suspect and r.winner == "tie"
