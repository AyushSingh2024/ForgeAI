"""Attach ONLY the tools the agent needs, each with a logged reason."""

from __future__ import annotations

from forge.guard.probes import TOOL_PATTERNS
from forge.schemas.agent_def import ToolBinding
from forge.schemas.corpus import CorpusProfile
from forge.schemas.groundability import GroundabilityReport
from forge.schemas.requirements import Requirements

ORDER = ["csv_lookup", "calculator", "current_date", "http_weather"]


def select_tools(req: Requirements, guard: GroundabilityReport | None, profile: CorpusProfile,
                 docs_prefix: str = "docs") -> list[ToolBinding]:
    reasons: dict[str, list[str]] = {}
    texts = [req.brief] + [f"{m.topic} {m.example_question}" for m in req.must_answer]

    if guard:
        for v in guard.verdicts:
            if v.needed_tool:
                reasons.setdefault(v.needed_tool, []).append(f"the guard found '{v.ask_text}' needs it")

    for name, pat in TOOL_PATTERNS.items():
        for t in texts:
            m = pat.search(t)
            if m:
                reasons.setdefault(name, []).append(f"asks mention '{m.group(0)}'")
                break

    if profile.tables:
        reasons.setdefault("csv_lookup", []).insert(0, f"the corpus has {len(profile.tables)} table(s): "
                                                       + ", ".join(t.name for t in profile.tables))
        # questions over tables almost always need counting / totals
        reasons.setdefault("calculator", []).append("table values may need totals or arithmetic")
    else:
        reasons.pop("csv_lookup", None)  # nothing to look up

    bindings = []
    for name in ORDER:
        if name not in reasons:
            continue
        config: dict = {}
        if name == "csv_lookup":
            config = {"tables": [{"name": t.name, "path": f"{docs_prefix}/{_rel(t.path)}"} for t in profile.tables]}
        bindings.append(ToolBinding(name=name, reason="; ".join(dict.fromkeys(reasons[name]))[:300],  # type: ignore[arg-type]
                                    config=config))
    return bindings


def _rel(path: str) -> str:
    """Path of a table file relative to the docs folder (input/docs/...)."""
    p = path.replace("\\", "/")
    for marker in ("/input/docs/", "/docs/"):
        if marker in p:
            return p.split(marker, 1)[1]
    return p.rsplit("/", 1)[-1]
