"""Fill the system-prompt slots. The fixed skeleton (prompts/agent_system_skeleton.md) holds the non-negotiable
rules; slots make targeted optimizer edits possible (one slot at a time, small readable diffs)."""

from __future__ import annotations

from forge.llm.client import LLMClient
from forge.schemas.agent_def import PromptSlots, ToolBinding
from forge.schemas.groundability import GroundabilityReport
from forge.schemas.requirements import Requirements

FORMAT_TEXT = {"prose": "Answer in short paragraphs.", "bullets": "Answer with concise bullet points.",
               "table": "Use a small markdown table when comparing several items, otherwise short sentences."}


def explicit_tool_rules(tools: list[ToolBinding]) -> str:
    """Deterministic when-to-call rules with an example call per tool. Small models skip tools without these."""
    lines = []
    for t in tools:
        if t.name == "csv_lookup":
            tables = [x["name"] for x in t.config.get("tables", [])]
            lines.append(f"ALWAYS call csv_lookup for any question about rows or values in the tables "
                         f"({', '.join(tables)}): counts, quantities, prices, which items match. Never answer these "
                         "from the table description passage. Example: {\"action\": \"call_tool\", \"tool\": "
                         f"\"csv_lookup\", \"args\": {{\"table\": \"{tables[0] if tables else 'name'}\", \"filters\": "
                         "[{\"column\": \"...\", \"op\": \"eq\", \"value\": \"...\"}], \"aggregate\": {\"op\": \"count\"}}}.")
        elif t.name == "calculator":
            lines.append("Never do arithmetic yourself: call calculator, e.g. {\"action\": \"call_tool\", \"tool\": "
                         "\"calculator\", \"args\": {\"expression\": \"12 * 34.5\"}}.")
        elif t.name == "current_date":
            lines.append("For anything relative to today (days left, still valid, expired), call current_date first.")
        elif t.name == "http_weather":
            lines.append("For weather or forecasts, call http_weather with the place name.")
    return " ".join(lines)


def template_slots(req: Requirements, tools: list[ToolBinding]) -> PromptSlots:
    refuse = "; ".join(m.topic for m in req.must_refuse)
    tool_rules = " ".join(f"Use {t.name} when {t.reason}." for t in tools)
    return PromptSlots(
        role=f"You are {req.agent_name}, an assistant that answers questions using the provided documents.",
        audience=f"{req.audience.who} ({req.audience.expertise} level). Adjust detail and jargon to them.",
        tone=f"{req.tone.style}; formality {req.tone.formality}.",
        scope="You help with: " + "; ".join(req.scope.in_scope or [m.topic for m in req.must_answer]) + "."
              + (f" Not in scope: {'; '.join(req.scope.out_of_scope)}." if req.scope.out_of_scope else ""),
        refusal_policy=f"Politely refuse these topics: {refuse}." if refuse else "",
        grounding="Only state facts present in the context passages or tool results. If something is not there, "
                  "say the documents do not cover it.",
        citation_rule="Every factual sentence needs a citation with an exact quote from the passage it came from.",
        tool_rules=tool_rules,
        format=FORMAT_TEXT.get(req.output_preferences.format, ""),
    )


def fill_slots(req: Requirements, guard: GroundabilityReport | None, tools: list[ToolBinding],
               llm: LLMClient) -> tuple[PromptSlots, bool]:
    base = template_slots(req, tools)
    if tools:
        base.tool_rules = (base.tool_rules + " " + explicit_tool_rules(tools)).strip()
    res = llm.complete("generator_slots", {
        "requirements": req.model_dump(include={"agent_name", "scope", "audience", "tone", "must_answer",
                                                "must_refuse", "output_preferences"}),
        "warnings": guard.warnings if guard else [], "tools": [t.model_dump() for t in tools],
        "template": base.model_dump()}, schema=PromptSlots, max_tokens=1200)
    if not res.ok:
        return base, True
    slots: PromptSlots = res.data
    # keep the guarantees even if the model dropped something
    merged = {}
    for name, value in slots.model_dump().items():
        value = (value or "").strip()
        merged[name] = value if len(value) >= 10 else getattr(base, name)
    refuse_topics = [m.topic for m in req.must_refuse]
    if refuse_topics and not all(t.lower()[:20] in merged["refusal_policy"].lower() for t in refuse_topics):
        merged["refusal_policy"] = base.refusal_policy
    if tools and not all(t.name in merged["tool_rules"] for t in tools):
        merged["tool_rules"] = base.tool_rules
    rules = explicit_tool_rules(tools)
    if not tools:
        merged["tool_rules"] = ""
    elif rules not in merged["tool_rules"]:
        merged["tool_rules"] = (merged["tool_rules"] + " " + rules).strip()
    return PromptSlots(**merged), False
