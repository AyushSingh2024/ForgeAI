"""Stage "intake" (Req 1): draft -> at most 5 questions -> answers -> Requirements + requirements.md."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from forge.context import RunContext
from forge.errors import AwaitingAnswers
from forge.intake.drafter import corpus_digest, draft_requirements
from forge.intake.proxy_user import answer_questions, load_answers_file, turn
from forge.intake.questioner import select_questions
from forge.intake.render import render_requirements_md
from forge.llm.client import LLMClient
from forge.schemas.corpus import CorpusProfile
from forge.schemas.requirements import (InterviewTurn, MustAnswer, MustRefuse, Question, Requirements,
                                        RequirementsDraft)
from forge.util import normalize, read_json, read_model, slugify, write_json

_KEEP = {"", "no", "none", "nothing", "keep", "ok", "okay", "fine", "n/a", "na", "-", "no changes", "looks good"}


class ListEdit(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


def _list_edit(llm: LLMClient, field: str, current: list[str], answer: str) -> ListEdit:
    res = llm.complete("intake_merge", {"field": field, "current": current, "answer": answer}, schema=ListEdit,
                       max_tokens=400)
    if res.ok:
        return res.data
    return ListEdit(add=[answer.strip()])


def merge(draft: RequirementsDraft, turns: list[InterviewTurn], llm: LLMClient) -> tuple[RequirementsDraft, list[str]]:
    d = draft.model_copy(deep=True)
    notes: list[str] = []
    for t in turns:
        ans = (t.answer or "").strip()
        if normalize(ans) in _KEEP:
            continue
        fp = t.field_path
        if fp == "audience.expertise":
            if ans.lower() in ("novice", "intermediate", "expert"):
                d.audience.expertise = ans.lower()  # type: ignore[assignment]
            else:
                d.audience.who = ans
        elif fp == "tone.style":
            d.tone.style = ans
            d.tone.formality = "high" if "formal" == ans.lower() else ("low" if "casual" in ans.lower() else "medium")
        elif fp == "output_preferences.format":
            if ans.lower() in ("prose", "bullets", "table"):
                d.output_preferences.format = ans.lower()  # type: ignore[assignment]
        elif fp == "scope.in_scope":
            e = _list_edit(llm, "topics in scope", d.scope.in_scope, ans)
            removed = {normalize(x) for x in e.remove}
            d.scope.in_scope = [x for x in d.scope.in_scope if normalize(x) not in removed] + e.add
            d.scope.out_of_scope += e.remove
        elif fp == "must_refuse":
            e = _list_edit(llm, "topics the assistant must refuse", [m.topic for m in d.must_refuse], ans)
            for x in e.add:
                d.must_refuse.append(MustRefuse(id=f"ru_{slugify(x, 20)}", topic=x, reason="requested in the interview",
                                                source="user"))
        elif fp == "must_answer":
            e = _list_edit(llm, "topics the assistant must answer", [m.topic for m in d.must_answer], ans)
            for x in e.add:
                d.must_answer.append(MustAnswer(id=f"a{len(d.must_answer) + 1}", topic=x, example_question=x,
                                                priority=1))
        else:
            notes.append(f"unhandled answer for {fp}: {ans}")
    return d, notes


def _ask_cli(questions: list[Question]) -> list[InterviewTurn]:
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print(f"[bold]A few questions ({len(questions)}) before I build the agent. Press Enter to keep my guess.[/bold]")
    turns = []
    for i, q in enumerate(questions, start=1):
        console.print(f"\n[cyan]{i}/{len(questions)}[/cyan] {q.text}  [dim]({q.why})[/dim]")
        if q.kind == "choice":
            ans = Prompt.ask("  answer", choices=q.options, default=q.default or q.options[0])
        else:
            ans = Prompt.ask("  answer", default=q.default or "")
        turns.append(turn(q, ans, "user"))
    return turns


def run_intake(ctx: RunContext) -> Requirements:
    profile = read_model(ctx.path("corpus_profile.json"), CorpusProfile)
    brief = ctx.brief
    llm = ctx.hub.builder
    corpus = corpus_digest(profile)

    draft_path = ctx.path("intake", "draft.json")
    if draft_path.exists():  # resuming after the web interview: reuse the same draft and questions
        draft = read_model(draft_path, RequirementsDraft)
        questions = [Question.model_validate(q) for q in read_json(ctx.path("intake", "questions.json"), [])]
    else:
        draft, degraded = draft_requirements(brief, profile, llm)
        if degraded:
            ctx.note("intake: the requirements draft used the deterministic fallback")
        min_q = 3 if ctx.mode in ("interactive_cli", "interactive_web") else 0
        questions = select_questions(draft, ctx.cfg.intake.max_questions, min_q)
        write_json(draft_path, draft)
        write_json(ctx.path("intake", "questions.json"), [q.model_dump() for q in questions])

    answers_file = load_answers_file(ctx.path("input", "answers.yaml"))
    if ctx.mode == "interactive_cli" and questions:
        turns = _ask_cli(questions)
    elif ctx.mode == "interactive_web" and questions:
        given = ctx.answers if ctx.answers is not None else read_json(ctx.path("intake", "answers.json"))
        if given is None:
            raise AwaitingAnswers([q.model_dump() for q in questions])
        if given.get("__skip__"):
            turns = answer_questions(questions, brief, corpus, llm, answers_file)
        else:
            turns = [turn(q, str(given.get(q.id, "")), "user") for q in questions]
    else:
        turns = answer_questions(questions, brief, corpus, llm, answers_file)

    merged, notes = merge(draft, turns, llm)
    assumptions = [f"{t.question} -> '{t.answer or 'kept default'}'" for t in turns if t.source == "assumed"]
    req = Requirements(run_id=ctx.run_id, brief=brief, agent_name=merged.agent_name, scope=merged.scope,
                       audience=merged.audience, tone=merged.tone, must_answer=merged.must_answer,
                       must_refuse=merged.must_refuse, output_preferences=merged.output_preferences,
                       interview=turns[:5], assumptions=assumptions + notes)
    save_requirements(ctx, req)
    ctx.emit("intake", "info", f"{len(questions)} question(s) asked, {len(assumptions)} assumed; "
                               f"{len(req.must_answer)} must-answer, {len(req.must_refuse)} must-refuse")
    return req


def save_requirements(ctx: RunContext, req: Requirements) -> None:
    write_json(ctx.path("requirements.json"), req)
    ctx.path("requirements.md").write_text(render_requirements_md(req), encoding="utf-8")


def requirements_hash(req: Requirements) -> str:
    return hashlib.sha256(req.model_dump_json().encode()).hexdigest()[:12]
