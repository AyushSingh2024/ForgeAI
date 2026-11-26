"""Show the intake interview working end to end in "interactive" mode (the same path the web UI uses).

1. The pipeline drafts requirements, picks up to 5 questions and PAUSES (AwaitingAnswers).
2. The questions are printed. Answers are read from the keyboard, or, with --auto, taken from the demo's
   answers.yaml (matched by field_path), standing in for the person.
3. The pipeline resumes with those answers (source = "user" in requirements.md) and runs to the report.

Run from backend/:   python demos/scripts/run_interview_demo.py hr_policy [--auto]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from forge.config import load_config  # noqa: E402
from forge.errors import AwaitingAnswers  # noqa: E402
from forge.intake.proxy_user import load_answers_file  # noqa: E402
from forge.pipeline import prepare_run, run  # noqa: E402


def main() -> None:
    demo = sys.argv[1] if len(sys.argv) > 1 else "hr_policy"
    auto = "--auto" in sys.argv
    src = BACKEND / "demos" / demo
    run_dir = BACKEND / "runs" / f"interview_{demo}"
    if not (run_dir / "input").exists():
        prepare_run(run_dir, (src / "brief.txt").read_text(encoding="utf-8"), src / "docs")
    cfg = load_config()
    log = lambda stage, status, msg: print(f"  [{stage}] {status} {msg}")  # noqa: E731
    try:
        run(run_dir, cfg, mode="interactive_web", on_event=log)
        print("finished without needing answers")
        return
    except AwaitingAnswers as wait:
        questions = wait.questions
    scripted = load_answers_file(src / "answers.yaml") if auto else {}
    answers = {}
    print(f"\nThe interviewer asks {len(questions)} question(s):")
    for i, q in enumerate(questions, 1):
        opts = f" [{' / '.join(q['options'])}]" if q.get("options") else ""
        print(f"\n{i}. {q['text']}{opts}\n   why: {q['why']}")
        if auto:
            a = scripted.get(q["field_path"], "")
            print(f"   answer: {a or '(keep default)'}")
        else:
            a = input("   your answer (Enter = keep default): ").strip()
        answers[q["id"]] = a
    (run_dir / "intake" / "answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    status = run(run_dir, cfg, mode="interactive_web", on_event=log)
    print(f"\nStatus: {status.get('status')}. Report: {run_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
