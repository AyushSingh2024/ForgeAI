"""Stratified train / holdout split. The optimizer only ever sees train results."""

from __future__ import annotations

import math
import random
from collections import defaultdict

from forge.schemas.eval_case import EvalCase


def assign_splits(cases: list[EvalCase], holdout_fraction: float = 0.25, seed: int = 7) -> list[EvalCase]:
    rng = random.Random(seed)
    by_cat: dict[str, list[EvalCase]] = defaultdict(list)
    for c in cases:
        by_cat[c.category].append(c)
    out = []
    for cat in sorted(by_cat):
        group = sorted(by_cat[cat], key=lambda c: c.id)
        rng.shuffle(group)
        n_hold = math.floor(len(group) * holdout_fraction) if len(group) >= 3 else 0
        if len(group) >= 3:
            n_hold = max(1, n_hold)
        for i, c in enumerate(group):
            out.append(c.model_copy(update={"split": "holdout" if i < n_hold else "train"}))
    return sorted(out, key=lambda c: c.id)
