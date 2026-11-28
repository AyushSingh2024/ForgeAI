"""Faster builds: independent model calls run in parallel, and the result must be identical to a sequential run."""

from __future__ import annotations

import json
import re
import threading
import time

import pytest

from forge.config import with_overrides
from forge.pipeline import prepare_run, run
from forge.util import pmap
from tests.test_pipeline_smoke import RESPONDER


def test_pmap_keeps_order_and_runs_concurrently():
    active, peak, lock = [0], [0], threading.Lock()

    def slow(x):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return x * x

    assert pmap(slow, range(8), 4) == [x * x for x in range(8)]
    assert peak[0] > 1
    assert pmap(slow, range(3), 1) == [0, 1, 4]


def test_pmap_reraises():
    def boom(x):
        if x == 2:
            raise ValueError("x")
        return x

    with pytest.raises(ValueError):
        pmap(boom, range(5), 3)


_VOLATILE = re.compile(r'("timestamp": "[^"]*"|created_at: \S+|requirements_hash: \S+)')


def _artifacts(run_dir):
    """Everything that matters, minus wall-clock timestamps (and the hash of requirements, which hold one)."""
    out = {}
    for rel in ("evals/cases.jsonl", "groundability.json", "agent/agent.yaml", "changelog.jsonl"):
        p = run_dir / rel
        out[rel] = _VOLATILE.sub("", p.read_text(encoding="utf-8")) if p.exists() else None
    for p in sorted((run_dir / "iterations").rglob("scorecard.json")):
        sc = json.loads(p.read_text(encoding="utf-8"))
        for c in sc["cases"]:
            c.pop("latency_ms", None)
        out[str(p.relative_to(run_dir))] = sc
    return out


def test_parallel_build_gives_the_same_artifacts_as_sequential(tmp_path, tiny_corpus, cfg, make_fake_hub):
    results = []
    for workers in (1, 4):
        c = with_overrides(cfg, "llm", concurrency=workers)
        hub = make_fake_hub(agent=RESPONDER, judge=RESPONDER)
        run_dir = prepare_run(tmp_path / f"w{workers}" / "run", "Help gym members with memberships and refunds.", tiny_corpus)
        run(run_dir, c, mode="unattended", hub=hub)
        results.append(_artifacts(run_dir))
    assert results[0] == results[1]
