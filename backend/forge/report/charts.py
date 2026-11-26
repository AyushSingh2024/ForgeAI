"""Simple charts for REPORT.md: a Mermaid xychart (renders on GitHub) and markdown tables."""

from __future__ import annotations

from forge.schemas.scorecard import Scorecard


def pass_rate_chart(points: list[tuple[str, float]]) -> str:
    if not points:
        return ""
    labels = ", ".join(f'"{p[0]}"' for p in points)
    values = ", ".join(f"{round(p[1] * 100, 1)}" for p in points)
    return ("```mermaid\nxychart-beta\n    title \"Pass rate by iteration (%)\"\n"
            f"    x-axis [{labels}]\n    y-axis \"pass rate %\" 0 --> 100\n    bar [{values}]\n```")


def category_table(first: Scorecard, best: Scorecard, holdout: Scorecard | None) -> str:
    cats = sorted(set(first.summary.by_category) | set(best.summary.by_category) |
                  set(holdout.summary.by_category if holdout else {}))
    rows = ["| category | baseline (train) | best (train) | holdout |", "|---|---|---|---|"]
    for c in cats:
        f = first.summary.by_category.get(c)
        b = best.summary.by_category.get(c)
        h = holdout.summary.by_category.get(c) if holdout else None
        rows.append(f"| {c} | {_pct(f)} | {_pct(b)} | {_pct(h)} |")
    return "\n".join(rows)


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.0%}"
