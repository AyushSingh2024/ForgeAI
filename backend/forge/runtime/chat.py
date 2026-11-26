"""Terminal chat loop for `forge chat agent.yaml` (Req 8)."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from forge.runtime.contract import render_for_chat
from forge.runtime.runner import AgentRuntime


def chat_loop(agent_path: Path) -> None:
    console = Console()
    rt = AgentRuntime.load(agent_path)
    a = rt.agent
    console.print(Panel(f"[bold]{a.name}[/bold] v{a.version}\n{a.description}\n"
                        f"Tools: {', '.join(a.tool_names()) or 'none'}\n"
                        "Type /quit to exit, /trace to show the last retrieval and tool calls.", title="ForgeAI agent"))
    if a.suggested_questions:
        console.print("Try: " + " | ".join(a.suggested_questions[:3]), style="dim")
    history: list[dict[str, str]] = []
    last_trace: dict | None = None
    while True:
        try:
            q = console.input("[bold cyan]you> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q in ("/quit", "/exit"):
            break
        if q == "/trace":
            if not last_trace:
                console.print("no trace yet", style="dim")
                continue
            t = Table("rank", "chunk", "page", "dense", "bm25")
            for i, h in enumerate(last_trace.get("hits", []), start=1):
                t.add_row(str(i), h["chunk_id"], str(h["page"]), str(h["dense"]), str(h["bm25"]))
            console.print(t)
            for tc in last_trace.get("tool_calls", []):
                console.print(f"tool {tc['tool']} args={tc['arguments']} -> {str(tc['result'])[:300]}", style="dim")
            continue
        with console.status("thinking..."):
            ans, last_trace = rt.answer(q, history)
        style = "yellow" if ans.refused else "green"
        console.print(Panel(render_for_chat(ans), border_style=style))
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": ans.answer}]
        history = history[-12:]
