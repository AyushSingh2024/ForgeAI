"""Req 6: the critic-optimizer loop. Classify failures -> one targeted fix -> re-score -> keep or revert.

Max 3 iterations; every change is logged with before/after scores in changelog.jsonl.
Entry point: forge.optimizer.loop.run_optimize (imported lazily to avoid an import cycle with forge.judge).
"""
