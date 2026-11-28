"""Regression mode (stretch goal): compare a new scorecard with an older one, case by case.

Used by `forge eval <agent.yaml> --cases cases.jsonl --against old_scorecard.json`. Only cases present in both
scorecards are compared, so a frozen eval set gives a fair before/after picture of one agent change.
"""

from __future__ import annotations

from typing import Any

from forge.schemas.scorecard import Scorecard


def diff_scorecards(old: Scorecard, new: Scorecard) -> dict[str, Any]:
    before = {c.case_id: c for c in old.cases}
    after = {c.case_id: c for c in new.cases}
    shared = sorted(before.keys() & after.keys())
    rows = []
    for cid in shared:
        b, a = before[cid].verdict, after[cid].verdict
        change = "unchanged" if a == b else ("fixed" if a == "pass" else "regressed")
        rows.append({"case": cid, "category": after[cid].category, "before": b, "after": a, "change": change,
                     "reason_after": after[cid].failure_reason if a == "fail" else ""})

    def rate(cards: dict, ids: list[str]) -> float | None:
        return round(sum(cards[i].verdict == "pass" for i in ids) / len(ids), 3) if ids else None

    return {
        "compared": len(shared),
        "only_in_old": sorted(before.keys() - after.keys()),
        "only_in_new": sorted(after.keys() - before.keys()),
        "pass_rate_before": rate(before, shared),
        "pass_rate_after": rate(after, shared),
        "fixed": [r["case"] for r in rows if r["change"] == "fixed"],
        "regressed": [r["case"] for r in rows if r["change"] == "regressed"],
        "cases": rows,
    }
