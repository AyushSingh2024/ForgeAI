"""The human-readable requirements document (requirements.md)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from forge.schemas.requirements import Requirements

_TEMPLATES = Path(__file__).resolve().parent.parent / "report" / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), trim_blocks=True, lstrip_blocks=True)


def _cell(text: str) -> str:
    return (text or "").replace("|", "/").replace("\n", " ")


def render_requirements_md(req: Requirements) -> str:
    _env.filters["cell"] = _cell
    return _env.get_template("requirements.md.j2").render(req=req)
