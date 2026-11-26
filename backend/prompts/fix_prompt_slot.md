---
id: fix_prompt_slot
version: 1
purpose: rewrite ONE system-prompt slot to fix a shared failure pattern (targeted fix, not regeneration)
inputs: [slots, examples, tried]
output_schema: SlotEdit
---
An assistant's system prompt is made of these slots:
{{ slots | tojson }}

It failed these test questions. The passage with the answer WAS retrieved, but the answer missed key facts or had
the wrong format:
{% for e in examples %}
- question: {{ e.question }}
  required facts: {{ e.key_facts | join("; ") }}
  actual answer: {{ e.answer }}
{% endfor %}

Slots already edited (choose a different one if possible): {{ tried | join(", ") or "none" }}

Choose the ONE slot whose change would most likely fix the shared problem, and rewrite it.
1. Keep the slot's original meaning; change it minimally.
2. Make it general. NEVER mention these specific questions, their facts or their answers.
3. slot_name must be one of: role, audience, tone, scope, refusal_policy, grounding, citation_rule, tool_rules, format.

Return JSON: {"rationale": "...", "slot_name": "...", "new_text": "..."}
