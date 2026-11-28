"""Stratified train / holdout split. The optimizer only ever sees train results.

Rules:
- At least `holdout_fraction` (25%) of all cases go to the holdout, rounded UP.
- When the eval set has at least `min_cases_for_floor` (20) cases, the holdout has at least `min_holdout` (5) cases,
  so its score is not decided by one or two answers.
- The holdout is spread over the categories in proportion to their size (largest remainder), and every category
  keeps at least one training case, so the optimizer can still see every kind of failure.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict

from forge.schemas.eval_case import EvalCase


def holdout_size(n_cases: int, holdout_fraction: float = 0.25, min_holdout: int = 5,
                 min_cases_for_floor: int = 20) -> int:
    """How many of n_cases go to the holdout."""
    if n_cases < 2:
        return 0
    n = math.ceil(n_cases * holdout_fraction - 1e-9)
    if n_cases >= min_cases_for_floor:
        n = max(n, min_holdout)
    return min(n, n_cases - 1)


def assign_splits(cases: list[EvalCase], holdout_fraction: float = 0.25, seed: int = 7, min_holdout: int = 5,
                  min_cases_for_floor: int = 20) -> list[EvalCase]:
    rng = random.Random(seed)
    by_cat: dict[str, list[EvalCase]] = defaultdict(list)
    for c in cases:
        by_cat[c.category].append(c)
    groups = {}
    for cat in sorted(by_cat):
        group = sorted(by_cat[cat], key=lambda c: c.id)
        rng.shuffle(group)
        groups[cat] = group

    total = holdout_size(len(cases), holdout_fraction, min_holdout, min_cases_for_floor)
    cap = {cat: max(0, len(g) - 1) for cat, g in groups.items()}  # keep >= 1 training case per category
    share = {cat: len(g) * total / max(1, len(cases)) for cat, g in groups.items()}
    quota = {cat: min(cap[cat], math.floor(share[cat])) for cat in groups}
    # hand out the rest by largest remainder, then by category size, never over a category's cap
    order = sorted(groups, key=lambda c: (-(share[c] - math.floor(share[c])), -len(groups[c]), c))
    left = total - sum(quota.values())
    while left > 0 and any(quota[c] < cap[c] for c in groups):
        for cat in order:
            if left == 0:
                break
            if quota[cat] < cap[cat]:
                quota[cat] += 1
                left -= 1

    out = []
    for cat, group in groups.items():
        for i, c in enumerate(group):
            out.append(c.model_copy(update={"split": "holdout" if i < quota[cat] else "train"}))
    return sorted(out, key=lambda c: c.id)
