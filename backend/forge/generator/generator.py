"""Stage "generate_agent" (Req 3): requirements + guard + profile -> self-contained agent folder with agent.yaml."""

from __future__ import annotations

import shutil

from forge.context import RunContext
from forge.generator.prompt_slots import fill_slots
from forge.generator.retrieval_params import choose_retrieval
from forge.generator.tool_selector import select_tools
from forge.intake.interviewer import requirements_hash
from forge.runtime.indexing import build_agent_index
from forge.runtime.prompting import render_system_prompt
from forge.schemas.agent_def import (AgentDefinition, CorpusRef, ModelCfg, OutputContract, Provenance, SystemPrompt,
                                     TableRef, save_agent)
from forge.schemas.corpus import CorpusProfile
from forge.schemas.groundability import GroundabilityReport
from forge.schemas.requirements import Requirements
from forge.util import read_model

REFUSAL = {"low": "Sorry, I can't help with that one, it isn't covered by the documents I have.",
           "medium": "I'm sorry, I can't help with that based on the documents I have.",
           "high": "I regret that I am unable to assist with this request based on the available documentation."}


def build_definition(req: Requirements, guard: GroundabilityReport | None, profile: CorpusProfile,
                     ctx: RunContext) -> tuple[AgentDefinition, list[str]]:
    notes = []
    tools = select_tools(req, guard, profile)
    retrieval = choose_retrieval(profile, ctx.cfg)
    slots, degraded = fill_slots(req, guard, tools, ctx.hub.builder)
    if degraded:
        notes.append("generator: system prompt slots used the template fallback")
    llm = ctx.cfg.llm
    csv = next((t for t in tools if t.name == "csv_lookup"), None)
    table_refs = [TableRef(**t) for t in csv.config.get("tables", [])] if csv else []
    agent = AgentDefinition(
        name=req.agent_name, version=1,
        description=(req.brief[:280] + ("..." if len(req.brief) > 280 else "")),
        model=ModelCfg(provider=llm.agent_provider, name=llm.agent_model, temperature=0.0, seed=ctx.cfg.judge.seed),
        system_prompt=SystemPrompt(slots=slots),
        corpus=CorpusRef(docs_dir="docs", index_dir="index", tables=table_refs),
        retrieval=retrieval, tools=tools,
        output_contract=OutputContract(max_words=max(80, min(400, req.output_preferences.max_words))),
        refusal_message=REFUSAL.get(req.tone.formality, REFUSAL["medium"]),
        suggested_questions=[m.example_question for m in req.must_answer if m.example_question][:5],
        provenance=Provenance(built_from_run=ctx.run_id, requirements_hash=requirements_hash(req)))
    agent.system_prompt.rendered = render_system_prompt(agent)
    return agent, notes


def run_generate_agent(ctx: RunContext) -> AgentDefinition:
    req = read_model(ctx.path("requirements.json"), Requirements)
    profile = read_model(ctx.path("corpus_profile.json"), CorpusProfile)
    guard = read_model(ctx.path("groundability.json"), GroundabilityReport) if ctx.path("groundability.json").exists() else None
    agent, notes = build_definition(req, guard, profile, ctx)
    for n in notes:
        ctx.note(n)

    agent_dir = ctx.path("agent")
    if (agent_dir / "docs").exists():
        shutil.rmtree(agent_dir / "docs")
    shutil.copytree(ctx.docs_dir, agent_dir / "docs")
    n_chunks = build_agent_index(agent, agent_dir, ctx.embedder())
    save_agent(agent, agent_dir / "agent.yaml")
    save_agent(agent, agent_dir / "versions" / "agent_v1.yaml")
    ctx.emit("generate_agent", "info", f"tools: {', '.join(agent.tool_names()) or 'none'}; "
                                       f"chunk_size {agent.retrieval.chunk_size}, top_k {agent.retrieval.top_k}; "
                                       f"{n_chunks} chunks indexed")
    return agent
