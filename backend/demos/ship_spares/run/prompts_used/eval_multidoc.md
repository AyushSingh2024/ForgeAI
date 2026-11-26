---
id: eval_multidoc
version: 1
purpose: a question whose full answer needs two passages from different documents
inputs: [audience, chunk_a, chunk_b]
output_schema: CaseDraftList
---
You write test questions for a document assistant used by: {{ audience }}.

<passage_a>
{{ chunk_a }}
</passage_a>

<passage_b>
{{ chunk_b }}
</passage_b>

Write ONE realistic question whose complete answer needs information from BOTH passages.
1. key_facts: at least one fact from passage A and one from passage B.
2. quotes: one sentence copied EXACTLY from passage A and one copied EXACTLY from passage B.
3. If the passages are unrelated, still write the most natural question that combines them.

Return JSON: {"cases": [{"question": "...", "expected_behavior": "answer", "key_facts": [{"fact": "...", "kind": "semantic"}], "quotes": ["exact sentence from A", "exact sentence from B"], "notes": ""}]}
