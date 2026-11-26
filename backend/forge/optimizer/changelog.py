"""Append-only change log of optimizer edits, plus a markdown table for the report."""

from __future__ import annotations

import difflib
from pathlib import Path

from forge.schemas.changelog import ChangeEntry
from forge.util import append_jsonl, read_jsonl


def append(run_dir: Path, entry: ChangeEntry) -> None:
    append_jsonl(run_dir / "changelog.jsonl", entry)


def read(run_dir: Path) -> list[ChangeEntry]:
    return read_jsonl(run_dir / "changelog.jsonl", ChangeEntry)


def text_diff(before: str, after: str) -> str:
    return "\n".join(difflib.unified_diff((before or "").splitlines(), (after or "").splitlines(), "before", "after",
                                         n=1, lineterm=""))


def _short(v) -> str:
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def to_markdown_table(entries: list[ChangeEntry]) -> str:
    if not entries:
        return "_No changes were made._"
    rows = ["| iter | failure class | change | cases targeted | pass rate before -> after | kept |",
            "|---|---|---|---|---|---|"]
    for e in entries:
        change = "; ".join(f"`{c.path}`: {_short(c.before)} -> {_short(c.after)}" for c in e.changes) or "-"
        change = change.replace("|", "/").replace("\n", " ")
        kept = "kept" if e.kept else f"reverted ({e.reverted_reason or 'no gain'})"
        rows.append(f"| {e.iteration} | {e.failure_class} | {change} | {', '.join(e.target_case_ids[:6])} | "
                    f"{e.score_before.overall:.0%} -> {e.score_after.overall:.0%} | {kept} |")
    return "\n".join(rows)
