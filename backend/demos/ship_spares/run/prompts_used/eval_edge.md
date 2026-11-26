---
id: eval_edge
version: 1
purpose: near-miss questions, close to the documents' topics but not answered by them
inputs: [audience, documents, n]
output_schema: CaseDraftList
---
You write test questions for a document assistant used by: {{ audience }}.
These are the documents it has:
{% for d in documents %}
- {{ d }}
{% endfor %}

Write {{ n }} question(s) that sound like they belong to this domain but that these documents most likely do NOT
answer (a related detail, a neighbouring topic, a specific case the documents do not mention). The correct
behaviour is to say the documents don't cover it, so expected_behavior = "refuse", no key facts, no quotes.

Return JSON: {"cases": [{"question": "...", "expected_behavior": "refuse", "key_facts": [], "quotes": [], "notes": "why it is not covered"}]}
