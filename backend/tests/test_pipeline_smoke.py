"""End to end: the whole factory on the tiny corpus with a scripted fake model (offline, a few seconds).

Checks that every artifact exists and validates, that the run can resume, and that the report is written.
"""

from __future__ import annotations

import re

from forge.pipeline import STAGES, prepare_run, run
from forge.schemas.agent_def import load_agent
from forge.schemas.eval_case import EvalCase
from forge.schemas.requirements import Requirements
from forge.schemas.scorecard import Scorecard
from forge.util import read_json, read_jsonl
from tests.conftest import scripted
from tests.test_intake import DRAFT


def _first_sentence(text: str) -> str:
    text = re.sub(r"^#+ .*\n", "", text.strip())
    m = re.search(r"[^.\n]{20,}?\.", text)
    return (m.group(0) if m else text[:80]).strip()


def _between(text: str, a: str, b: str) -> str:
    return text.split(a, 1)[1].split(b, 1)[0] if a in text else ""


def _user(m):
    return next(x["content"] for x in reversed(m) if x["role"] == "user")


def agent_reply(m):
    ctx = _user(m)
    c1 = _between(ctx, "[C1]", "[C2]") or _between(ctx, "[C1]", "QUESTION")
    body = c1.split("\n", 1)[1] if "\n" in c1 else c1
    s = _first_sentence(body)
    return {"action": "final", "answer": s, "citations": [{"chunk_id": "C1", "quote": s}], "refused": False,
            "confidence": 0.7}


def answerable(m):
    s = _first_sentence(_between(_user(m), "<passage>", "</passage>"))
    word = (re.findall(r"[A-Za-z]{6,}", s) or ["policy"])[0]
    return {"cases": [{"question": f"What do the rules say about {word.lower()}?", "expected_behavior": "answer",
                       "key_facts": [{"fact": s, "kind": "semantic"}], "quotes": [s]}]}


def two(m, behavior):
    u = _user(m)
    a = _first_sentence(_between(u, "<passage_a>", "</passage_a>"))
    b = _first_sentence(_between(u, "<passage_b>", "</passage_b>"))
    return {"cases": [{"question": f"How do these compare ({len(a)})?", "expected_behavior": behavior,
                       "key_facts": [{"fact": a}, {"fact": b}], "quotes": [a, b], "notes": "two readings"}]}


RESPONDER = scripted([
    ("NON-NEGOTIABLE RULES", agent_reply),
    ("designing a question-answering assistant", DRAFT),
    ("standing in for the person", {"answers": []}),
    ("realistic questions a user would ask", lambda m: {"probes": [_user(m).split('"')[1]]}),
    ("List each distinct piece", {"asks": []}),
    ("Decide if the passages contain the answer", {"reasoning": "", "supported": False}),
    ("You write test questions", lambda m: (
        two(m, "clarify") if "could reasonably mean" in _user(m) else
        two(m, "answer") if "<passage_a>" in _user(m) else
        {"cases": [{"question": "Can you recommend a diet for weight loss?", "expected_behavior": "refuse", "notes": "medical advice"},
                   {"question": "What is the capital of Australia?", "expected_behavior": "refuse", "notes": "off-domain"},
                   {"question": "Do you sell protein shakes at the bar?", "expected_behavior": "refuse", "notes": "near miss"}]}
        if ("MUST refuse" in _user(m) or "most likely do NOT" in _user(m)) else answerable(m))),
    ("wants this information from a data table", {"question": "How many of those classes are there?"}),
    ("Is the fact stated in", {"reasoning": "", "entailed": True}),
    ("strict, fair grader", {"rationale": "ok", "faithfulness": 4, "relevance": 4, "tone": 4, "ambiguity_handling": 3}),
    ("Decide which answer is better", {"rationale": "same", "winner": "tie"}),
    ("rewrite it", {"rationale": "be complete", "slot_name": "format",
                    "new_text": "Answer completely and include every number and condition."}),
    ("Summarise what this document is", {"summary": "A short policy document."}),
])


def test_full_factory_run(tmp_path, tiny_corpus, cfg, make_fake_hub):
    hub = make_fake_hub(agent=RESPONDER, judge=RESPONDER)
    run_dir = prepare_run(tmp_path / "runs" / "smoke", "Help members of a gym with memberships, refunds, opening "
                                                      "hours and the class timetable. Do not give medical advice.",
                          tiny_corpus)
    status = run(run_dir, cfg, mode="unattended", hub=hub)
    assert status["status"] in ("completed", "budget_stopped"), status

    Requirements.model_validate(read_json(run_dir / "requirements.json"))
    agent = load_agent(run_dir / "agent" / "agent.yaml")
    cases = read_jsonl(run_dir / "evals" / "cases.jsonl", EvalCase)
    assert cases and {"must_refuse", "answerable"} <= {c.category for c in cases}
    assert any(c.split == "holdout" for c in cases)
    Scorecard.model_validate(read_json(run_dir / "iterations" / "0" / "scorecard.json"))
    assert (run_dir / "iterations" / "final_holdout" / "scorecard.json").exists()
    report = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    for section in ("## 1. Summary", "## 7. Change log", "## 8. Judge reliability", "## 9. Known failures"):
        assert section in report
    assert (run_dir / "prompts_used").exists()
    assert agent.version >= 1

    # resume: only the report is redone
    (run_dir / ".stages" / "report.done").unlink()
    before = (run_dir / "iterations" / "0" / "scorecard.json").stat().st_mtime
    run(run_dir, cfg, mode="unattended", hub=hub)
    assert (run_dir / "iterations" / "0" / "scorecard.json").stat().st_mtime == before
    assert all((run_dir / ".stages" / f"{s}.done").exists() for s in STAGES)
