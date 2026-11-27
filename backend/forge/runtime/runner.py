"""AgentRuntime: the one place where an agent answers a question (Req 8).

Generic: loads ANY agent.yaml. Used by `forge chat`, the eval harness and the /chat API route, so what is
tested is exactly what ships. Tool use goes through a JSON action protocol that works on every provider:
the model replies {"action": "call_tool", ...} or {"action": "final", ...}.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig, load_config
from forge.llm.budget import BudgetCfg
from forge.errors import BudgetExceeded, ProviderError
from forge.llm.client import LLMClient, make_hub
from forge.llm.repair import extract_json
from forge.retrieval.embedder import get_embedder
from forge.retrieval.hybrid import Hit, HybridRetriever
from forge.runtime.contract import enforce
from forge.runtime.indexing import ensure_index
from forge.runtime.prompting import render_system_prompt
from forge.runtime.tools import Tool, build_tools
from forge.schemas.agent_def import AgentDefinition, load_agent
from forge.schemas.answer import AgentAnswer, ToolCallRecord


def _context_block(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, start=1):
        c = h.chunk
        section = " > ".join(c.section_path)
        head = f"[C{i}] source={c.doc_id} page={c.page}" + (f" section=\"{section}\"" if section else "")
        parts.append(f"{head}\n{c.text.strip()}")
    return "\n\n".join(parts) if parts else "(no relevant passages found)"


class AgentRuntime:
    # set for chat: every answer gets a fresh allowance instead of sharing one budget for the server's lifetime
    per_answer_budget: BudgetCfg | None = None

    def __init__(self, agent: AgentDefinition, agent_dir: Path, llm: LLMClient, cfg: ForgeConfig,
                 retriever: HybridRetriever, tools: dict[str, Tool]):
        self.agent = agent
        self.agent_dir = agent_dir
        self.llm = llm
        self.cfg = cfg
        self.retriever = retriever
        self.tools = tools
        tool_desc = "\n".join(t.describe() for t in tools.values())
        self.system_prompt = render_system_prompt(agent, tool_desc)

    @classmethod
    def load(cls, agent: AgentDefinition | str | Path, *, agent_dir: Path | None = None,
             cfg: ForgeConfig | None = None, llm: LLMClient | None = None,
             rewrite_llm: LLMClient | None = None,
             per_answer_budget: BudgetCfg | None = None) -> "AgentRuntime":
        if not isinstance(agent, AgentDefinition):
            agent_dir = Path(agent).resolve().parent
            agent = load_agent(agent)
        if agent_dir is None:
            raise ValueError("agent_dir is required when passing an AgentDefinition")
        cfg = cfg or load_config()
        llm = llm or make_hub(cfg).agent
        embedder = get_embedder(cfg.llm.embedder)
        ensure_index(agent, agent_dir, embedder)
        retriever = HybridRetriever.from_index(agent_dir / agent.corpus.index_dir, agent.retrieval,
                                               llm=rewrite_llm or llm)
        tools = build_tools(agent.tools, agent_dir)
        rt = cls(agent, agent_dir, llm, cfg, retriever, tools)
        rt.per_answer_budget = per_answer_budget
        return rt

    # ------------------------------------------------------------------ answer
    def answer(self, question: str, history: list[dict[str, str]] | None = None) -> tuple[AgentAnswer, dict[str, Any]]:
        if self.per_answer_budget is not None:
            self.llm.budget.reset(self.per_answer_budget)
        t0 = time.perf_counter()
        trace: dict[str, Any] = {"question": question, "tool_calls": [], "raw_outputs": [], "tokens": 0,
                                 "deterministic_refusal": False, "error": None}
        hits = self.retriever.search(question)
        trace["hits"] = [{"chunk_id": h.chunk_id, "doc_id": h.chunk.doc_id, "page": h.chunk.page,
                          "score": round(h.score, 5), "dense": round(h.dense_score, 4), "bm25": round(h.bm25_score, 3),
                          "text": h.chunk.text[:6000]} for h in hits]
        best = HybridRetriever.best_score(hits)
        trace["best_score"] = round(best, 4)

        if best < self.agent.retrieval.min_score and not self.tools:
            trace["deterministic_refusal"] = True
            trace["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            return AgentAnswer(answer=self.agent.refusal_message, refused=True,
                               refusal_reason="no relevant passage in the documents", confidence=0.9), trace

        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        for turn in (history or [])[-6:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": str(turn["content"])[:2000]})
        low_note = "\nNOTE: the passages may not be relevant (low retrieval score)." if best < self.agent.retrieval.min_score else ""
        messages.append({"role": "user", "content": f"CONTEXT\n{_context_block(hits)}{low_note}\n\nQUESTION\n{question}"})

        tool_records: list[ToolCallRecord] = []
        final: dict[str, Any] | str | None = None
        hops = self.cfg.runtime.max_tool_hops if self.tools else 0
        try:
            for step in range(hops + 1):
                res = self.llm.chat(messages, temperature=self.agent.model.temperature,
                                    max_tokens=self.agent.model.max_tokens, json_mode=True)
                trace["tokens"] += res.tokens
                trace["raw_outputs"].append(res.text[:3000])
                data = extract_json(res.text)
                if isinstance(data, dict) and data.get("action") == "call_tool" and self.tools and step < hops:
                    name = str(data.get("tool", ""))
                    args = data.get("args") or data.get("arguments") or {}
                    tool = self.tools.get(name)
                    if tool is None:
                        result_text = json.dumps({"ok": False, "error": f"unknown tool {name}. Available: {list(self.tools)}"})
                        tool_records.append(ToolCallRecord(tool=name, arguments=args, error="unknown tool"))
                    else:
                        tr = tool.run(args)
                        tool_records.append(ToolCallRecord(tool=name, arguments=args, result=tr.data, error=tr.error))
                        result_text = json.dumps({"ok": tr.ok, "data": tr.data, "error": tr.error}, default=str)[:4000]
                    messages.append({"role": "assistant", "content": res.text})
                    messages.append({"role": "user", "content": f"TOOL RESULT ({name}): {result_text}\n"
                                                                "Call another tool or give the final answer JSON."})
                    continue
                final = data if isinstance(data, dict) else res.text
                break
            if final is None:  # ran out of hops: force a final answer
                messages.append({"role": "user", "content": "Give the final answer JSON now (action=final)."})
                res = self.llm.chat(messages, temperature=0.0, max_tokens=self.agent.model.max_tokens, json_mode=True)
                trace["tokens"] += res.tokens
                trace["raw_outputs"].append(res.text[:3000])
                final = extract_json(res.text) or res.text
        except BudgetExceeded:
            raise
        except ProviderError as exc:
            trace["error"] = str(exc)
            final = {"answer": "Sorry, the language model is unavailable right now.", "refused": False,
                     "confidence": 0.0}

        answer, extras = enforce(final, [h.chunk for h in hits], tool_records, self.agent.output_contract,
                                 self.agent.refusal_message)
        trace.update(extras)
        trace["tool_calls"] = [t.model_dump(mode="json") for t in tool_records]
        trace["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return answer, trace
