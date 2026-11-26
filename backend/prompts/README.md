# Prompts

Every prompt the factory sends to a model lives here, versioned and committed (Req 4). `forge/llm/prompts.py`
loads them, and each run copies the prompts it used into `runs/<id>/prompts_used/`.

Format: YAML front matter (`id`, `version`, `purpose`, `inputs`, `output_schema`), then a Jinja2 body.
Bump `version` on every edit.

Rules for small (7-9B) models: short numbered instructions, the key rule first and last, an exact JSON shape,
long material inside clear tags, the rationale before the verdict, and no domain-specific words (these prompts
must work for any brief).

| prompt | stage | output |
|---|---|---|
| doc_summary | ingest | Summary |
| intake_draft | intake | RequirementsDraft |
| intake_merge | intake | ListEdit |
| proxy_user | intake (unattended) | ProxyAnswers |
| guard_extract_asks | guard | AskList |
| guard_probe | guard | ProbeList |
| guard_verify | guard, eval validator | VerifyResult |
| generator_slots | generator | PromptSlots |
| agent_system_skeleton | runtime | text (fixed rules + slots) |
| query_rewrite | runtime (optional) | Rewrites |
| eval_answerable / eval_multidoc / eval_refuse / eval_ambiguous / eval_edge | evals | CaseDraftList |
| eval_tool_phrase | evals | PhrasedQuestion |
| eval_fact_check | eval validator | FactCheck |
| judge_rubric | judge | JudgeScores |
| judge_pairwise | judge, optimizer tie-break | PairVerdict |
| critic | optimizer | CriticVerdict |
| fix_prompt_slot | optimizer | SlotEdit |
| report_narrative | report | Narrative |
| repair_json | llm client | same as the failed call |
