---
id: guard_verify
version: 1
purpose: decide whether retrieved passages answer a question, with an exact supporting quote
inputs: [question, passages]
output_schema: VerifyResult
---
Question: {{ question }}

Passages:
{% for p in passages %}
<passage id="{{ p.id }}">
{{ p.text }}
</passage>
{% endfor %}

Decide if the passages contain the answer to the question.
1. "supported" is true ONLY if a passage states the answer. Related but incomplete information is not enough.
2. If supported, copy the supporting sentence EXACTLY into "quote" (it will be checked character by character) and
   put the passage id in "chunk_id".
3. If not supported, say briefly what is missing in "missing".
4. If the question needs live data or a calculation that no document could contain, set "needs_tool" to one of:
   http_weather, current_date, calculator, csv_lookup. Otherwise null.
Write "reasoning" first, in one or two sentences.

Return JSON: {"reasoning": "...", "supported": false, "chunk_id": null, "quote": "", "missing": "", "needs_tool": null}
