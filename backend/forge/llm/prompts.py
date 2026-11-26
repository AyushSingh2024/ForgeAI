"""Load and render the versioned prompt templates in backend/prompts/ (front matter + Jinja2 body)."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

from forge.config import PROMPTS_DIR

_env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=False)


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: int
    body: str
    sha: str
    path: Path


@lru_cache(maxsize=64)
def load_prompt(prompt_id: str, prompts_dir: Path = PROMPTS_DIR) -> PromptTemplate:
    path = prompts_dir / f"{prompt_id}.md"
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        meta = yaml.safe_load(front) or {}
    body = body.strip()
    return PromptTemplate(id=meta.get("id", prompt_id), version=int(meta.get("version", 1)), body=body,
                          sha=hashlib.sha256(body.encode()).hexdigest()[:12], path=path)


def render(prompt_id: str, **variables) -> str:
    tpl = load_prompt(prompt_id)
    return _env.from_string(tpl.body).render(**variables)


def snapshot(run_dir: Path, prompt_ids: set[str]) -> None:
    """Copy the prompts used in a run into runs/<id>/prompts_used/ (Req 4: generation prompts are committed)."""
    out = run_dir / "prompts_used"
    out.mkdir(parents=True, exist_ok=True)
    for pid in sorted(prompt_ids):
        try:
            shutil.copy2(load_prompt(pid).path, out / f"{pid}.md")
        except FileNotFoundError:
            continue
