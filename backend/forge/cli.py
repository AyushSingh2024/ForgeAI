"""The `forge` command line (Typer). Same pipeline as the API.

    forge build --brief brief.txt --docs ./docs [--unattended] [--answers answers.yaml]
    forge chat runs/<id>/agent/agent.yaml
    forge ask runs/<id>/agent/agent.yaml "question" [--json]
    forge eval runs/<id>/agent/agent.yaml --cases runs/<id>/evals/cases.jsonl     (regression mode)
    forge report runs/<id>
    forge doctor
Exit codes: 0 finished (even if quality is low), 2 bad input, 3 provider unreachable.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import typer
from rich.console import Console
from rich.table import Table

from forge.config import BACKEND_DIR, load_config, with_overrides
from forge.errors import AwaitingAnswers, BadInput
from forge.llm.client import make_hub, same_family

app = typer.Typer(add_completion=False, help="ForgeAI: brief + documents in, tested agent out.")
console = Console()


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]


def _read_brief(brief: str) -> str:
    p = Path(brief)
    return p.read_text(encoding="utf-8") if p.exists() else brief


@app.command()
def build(brief: str = typer.Option(..., help="Path to a brief.txt, or the brief text itself"),
          docs: Path = typer.Option(..., exists=True, file_okay=False, help="Folder with the documents"),
          unattended: bool = typer.Option(False, help="No questions: assume answers (review mode)"),
          answers: Path | None = typer.Option(None, help="answers.yaml with scripted interview answers"),
          out: Path = typer.Option(BACKEND_DIR / "runs", help="Where run folders are created"),
          run_id: str | None = typer.Option(None, help="Resume or name a run"),
          from_stage: str | None = typer.Option(None, help="Re-run from this stage"),
          max_iterations: int | None = typer.Option(None, help="Optimizer iterations (default 3)")) -> None:
    """Run the whole factory and print where the report is."""
    from forge.pipeline import prepare_run, run

    cfg = load_config()
    if max_iterations is not None:
        cfg = with_overrides(cfg, "optimizer", max_iterations=max_iterations)
    if same_family(cfg):
        console.print("[yellow]warning: agent and judge models are the same family (self-preference bias)[/yellow]")
    run_dir = out / (run_id or new_run_id())
    if not (run_dir / "input" / "brief.txt").exists():
        prepare_run(run_dir, _read_brief(brief), docs, answers)
    console.print(f"[bold]ForgeAI[/bold] run [cyan]{run_dir.name}[/cyan] -> {run_dir}")

    def on_event(stage: str, status: str, message: str) -> None:
        icon = {"running": "[cyan]>[/cyan]", "done": "[green]ok[/green]", "failed": "[red]x[/red]",
                "skipped": "[dim]-[/dim]", "info": "  [dim]", "waiting": "[yellow]?[/yellow]"}.get(status, status)
        console.print(f"{icon} {stage} {message}" + ("[/dim]" if status == "info" else ""))

    mode = "unattended" if unattended else "interactive_cli"
    try:
        status = run(run_dir, cfg, mode=mode, on_event=on_event, from_stage=from_stage)
    except BadInput as exc:
        console.print(f"[red]bad input:[/red] {exc}")
        raise typer.Exit(2)
    except AwaitingAnswers:
        console.print("[yellow]waiting for interview answers[/yellow]")
        raise typer.Exit(0)
    report = run_dir / "REPORT.md"
    console.print(f"\nStatus: [bold]{status.get('status')}[/bold]. Report: {report}")
    console.print(f"Chat with it: forge chat {run_dir / 'agent' / 'agent.yaml'}")


@app.command()
def chat(agent_yaml: Path = typer.Argument(..., exists=True)) -> None:
    """Interactive chat with any agent definition (Req 8)."""
    from forge.runtime.chat import chat_loop

    chat_loop(agent_yaml)


@app.command()
def ask(agent_yaml: Path = typer.Argument(..., exists=True), question: str = typer.Argument(...),
        as_json: bool = typer.Option(False, "--json")) -> None:
    """One-shot answer, for scripts."""
    from forge.runtime.contract import render_for_chat
    from forge.runtime.runner import AgentRuntime

    rt = AgentRuntime.load(agent_yaml)
    ans, trace = rt.answer(question)
    if as_json:
        sys.stdout.write(json.dumps({"answer": ans.model_dump(mode="json"), "trace": trace}, default=str, indent=2) + "\n")
    else:
        console.print(render_for_chat(ans))


@app.command(name="eval")
def eval_cmd(agent_yaml: Path = typer.Argument(..., exists=True), cases: Path = typer.Option(..., exists=True),
             against: Path | None = typer.Option(None, help="An earlier scorecard.json to diff verdicts against")) -> None:
    """Regression mode: score an agent on a frozen eval set, optionally diffing against an old scorecard."""
    from forge.evals.harness import run_cases
    from forge.judge.scorer import score_iteration
    from forge.runtime.runner import AgentRuntime
    from forge.schemas.agent_def import load_agent
    from forge.schemas.eval_case import EvalCase
    from forge.schemas.scorecard import JudgeReliability, Scorecard
    from forge.util import read_json, read_jsonl

    cfg = load_config()
    hub = make_hub(cfg)
    agent = load_agent(agent_yaml)
    rt = AgentRuntime.load(agent_yaml, cfg=cfg, llm=hub.agent)
    cs = read_jsonl(cases, EvalCase)
    transcripts = run_cases(rt, cs)
    sc = score_iteration(run_id="regression", iteration=0, agent_version=agent.version, cases=cs,
                         transcripts=transcripts, hub=hub, cfg=cfg, max_words=agent.output_contract.max_words,
                         tone="as specified", reliability=JudgeReliability(), split="all")
    console.print(f"pass rate {sc.summary.pass_rate:.0%} on {sc.summary.n_cases} cases; by category {sc.summary.by_category}")
    if against:
        old = {c.case_id: c.verdict for c in Scorecard.model_validate(read_json(against)).cases}
        t = Table("case", "before", "after")
        for c in sc.cases:
            if c.case_id in old and old[c.case_id] != c.verdict:
                t.add_row(c.case_id, old[c.case_id], c.verdict)
        console.print(t if t.row_count else "no verdict changes")


@app.command()
def report(run_dir: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Rebuild REPORT.md from a run's artifacts."""
    from forge.context import RunContext
    from forge.report.builder import build_report

    cfg = load_config()
    ctx = RunContext(run_dir=run_dir, cfg=cfg, hub=make_hub(cfg))
    console.print(f"written {build_report(ctx)}")


@app.command()
def doctor() -> None:
    """Pre-flight checks: providers reachable, models pulled, embedder loads."""
    from forge.retrieval.embedder import get_embedder

    cfg = load_config()
    hub = make_hub(cfg)
    ok_all = True
    for role, client in (("agent", hub.agent), ("judge", hub.judge)):
        ok, msg = client.health()
        ok_all &= ok
        console.print(f"{'[green]ok[/green]' if ok else '[red]FAIL[/red]'} {role} {client.model_id}: {msg}")
    emb = get_embedder(cfg.llm.embedder)
    console.print(f"[green]ok[/green] embedder backend={emb.backend} model={emb.name}")
    if same_family(cfg):
        console.print("[yellow]warning: agent and judge are the same model family[/yellow]")
    if not ok_all:
        raise typer.Exit(3)


if __name__ == "__main__":
    app()
