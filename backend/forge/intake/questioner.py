"""Choose the at most 5 questions worth asking (hard cap in code), as closed-form templates."""

from __future__ import annotations

from forge.schemas.requirements import Question, RequirementsDraft

WEIGHTS = {"scope": 5, "must_refuse": 4, "must_answer": 4, "audience": 3, "tone": 2, "output_preferences": 1}
THRESHOLD = 0.85


def _question(field: str, d: RequirementsDraft, idx: int) -> Question:
    qid = f"q{idx}"
    if field == "scope":
        cur = ", ".join(d.scope.in_scope[:6]) or "the topics in the documents"
        return Question(id=qid, field_path="scope.in_scope", kind="free_text", why="sets what the agent will answer",
                        text=f"I plan to cover: {cur}. Anything to add or leave out? (Enter keeps this)")
    if field == "must_refuse":
        cur = "; ".join(m.topic for m in d.must_refuse[:4]) or "nothing specific yet"
        return Question(id=qid, field_path="must_refuse", kind="free_text", why="the agent will decline these topics",
                        text=f"Besides: {cur}, is there anything it must refuse to discuss?")
    if field == "must_answer":
        cur = "; ".join(m.topic for m in d.must_answer[:5])
        return Question(id=qid, field_path="must_answer", kind="free_text", why="these become test questions",
                        text=f"The most important things it must answer seem to be: {cur}. Anything critical missing?")
    if field == "audience":
        return Question(id=qid, field_path="audience.expertise", kind="choice",
                        options=["novice", "intermediate", "expert"], default=d.audience.expertise,
                        why="changes how much detail and jargon to use",
                        text=f"Who will use it? My guess is {d.audience.who}. How expert are they?")
    if field == "tone":
        return Question(id=qid, field_path="tone.style", kind="choice",
                        options=["friendly and casual", "clear and professional", "formal"], default=d.tone.style,
                        why="sets the writing style", text="Which tone should the answers have?")
    return Question(id=qid, field_path="output_preferences.format", kind="choice", options=["prose", "bullets", "table"],
                    default=d.output_preferences.format, why="sets the answer layout",
                    text="How should answers be laid out?")


def select_questions(draft: RequirementsDraft, max_questions: int = 5, min_questions: int = 0) -> list[Question]:
    """Uncertain fields first (ranked by impact x uncertainty). When a person is present (min_questions > 0) the
    highest-impact fields are confirmed too, because models tend to be over-confident about briefs."""
    cap = min(5, max(0, max_questions))
    conf = draft.confidence.model_dump()
    ranked = sorted(WEIGHTS, key=lambda f: -(WEIGHTS[f] * (1 - float(conf.get(f, 0.5))) + WEIGHTS[f] * 1e-3))
    chosen = [f for f in ranked if float(conf.get(f, 0.5)) < THRESHOLD]
    for f in ranked:
        if len(chosen) >= min(min_questions, cap):
            break
        if f not in chosen:
            chosen.append(f)
    return [_question(f, draft, i + 1) for i, f in enumerate(chosen[:cap])]
