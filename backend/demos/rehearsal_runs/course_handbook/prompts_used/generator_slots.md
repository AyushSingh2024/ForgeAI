---
id: generator_slots
version: 1
purpose: write the brief-specific parts (slots) of the agent's system prompt
inputs: [requirements, warnings, tools, template]
output_schema: PromptSlots
---
You are writing parts of the system prompt for a document question-answering assistant.

Requirements:
{{ requirements | tojson }}

Warnings from the document check (asks the documents cannot fully support):
{% for w in warnings %}
- {{ w }}
{% else %}
- none
{% endfor %}

Attached tools:
{% for t in tools %}
- {{ t.name }}: {{ t.reason }}
{% else %}
- none
{% endfor %}

A plain draft of each slot:
{{ template | tojson }}

Improve each slot so it is specific to these requirements:
1. Each slot is 1 to 4 sentences in the imperative voice ("Answer...", "Refuse...").
2. refusal_policy must name EVERY must_refuse topic.
3. tool_rules must say WHEN to call each attached tool. Leave it empty if there are no tools.
4. Do not promise anything the warnings say the documents cannot support.
5. Do not include example answers or facts; the facts come from the documents at answer time.

Return JSON with keys: role, audience, tone, scope, refusal_policy, grounding, citation_rule, tool_rules, format.
