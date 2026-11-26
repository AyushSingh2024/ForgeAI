---
id: guard_extract_asks
version: 3
purpose: list the INFORMATION the brief expects the assistant to provide (not style or behaviour rules)
inputs: [brief, must_answer]
output_schema: AskList
---
List each distinct piece of INFORMATION or calculation the BRIEF explicitly expects the assistant to provide to
its users (for example "notice period for cancelling", "estimate the cost of an order", "weather at the port").
1. Only list what the brief actually says. Do NOT add generic abilities the brief does not mention.
2. Do NOT list style or behaviour rules (tone, citing sources, refusing topics, redirecting people to someone).
3. Do not merge different asks, and skip anything already covered by: {{ must_answer | join("; ") }}
4. If nothing new is left, return an empty list.

<brief>
{{ brief }}
</brief>

Return JSON: {"asks": [{"id": "b1", "text": "short description of the information asked for"}]}
