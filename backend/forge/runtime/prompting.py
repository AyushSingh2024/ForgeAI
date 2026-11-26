"""Render an agent's system prompt from its slots (shared by the generator and the runtime)."""

from __future__ import annotations

from forge.llm.prompts import render
from forge.schemas.agent_def import AgentDefinition


def render_system_prompt(agent: AgentDefinition, tool_descriptions: str = "") -> str:
    s = agent.system_prompt.slots
    return render("agent_system_skeleton", slots=s.model_dump(), few_shots=[f.model_dump() for f in
                                                                             agent.system_prompt.few_shots],
                  refusal_message=agent.refusal_message, max_words=agent.output_contract.max_words,
                  tool_descriptions=tool_descriptions, has_tools=bool(agent.tools))
