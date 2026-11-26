"""Answer the interview when nobody is there (unattended mode and the review run)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from forge.llm.client import LLMClient
from forge.schemas.requirements import InterviewTurn, Question


class ProxyAnswer(BaseModel):
    question_id: str
    answer: str = ""


class ProxyAnswers(BaseModel):
    answers: list[ProxyAnswer] = Field(default_factory=list)


def load_answers_file(path: Path) -> dict[str, str]:
    """answers.yaml: a list of {field_path|question_id, answer} or a plain mapping key -> answer."""
    if not path.exists():
        return {}
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    if isinstance(data, dict):
        out = {str(k): str(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "answer" in item:
                key = item.get("field_path") or item.get("question_id")
                if key:
                    out[str(key)] = str(item["answer"])
    return out


def turn(q: Question, answer: str, source: str) -> InterviewTurn:
    return InterviewTurn(question_id=q.id, field_path=q.field_path, question=q.text, why_asked=q.why,
                         answer=answer, source=source)  # type: ignore[arg-type]


def answer_questions(questions: list[Question], brief: str, corpus: str, llm: LLMClient,
                     answers_file: dict[str, str] | None = None) -> list[InterviewTurn]:
    answers_file = answers_file or {}
    turns: dict[str, InterviewTurn] = {}
    remaining = []
    for q in questions:
        a = answers_file.get(q.field_path) or answers_file.get(q.id) or answers_file.get(q.field_path.split(".")[0])
        if a is not None:
            turns[q.id] = turn(q, a, "answers_file")
        else:
            remaining.append(q)
    if remaining:
        res = llm.complete("proxy_user", {"brief": brief, "corpus": corpus,
                                          "questions": [q.model_dump() for q in remaining]},
                           schema=ProxyAnswers, max_tokens=700)
        got = {a.question_id: a.answer for a in res.data.answers} if res.ok else {}
        for q in remaining:
            ans = (got.get(q.id) or "").strip()
            if q.kind == "choice" and ans not in q.options:
                ans = q.default
            turns[q.id] = turn(q, ans or q.default, "assumed")
    return [turns[q.id] for q in questions]
