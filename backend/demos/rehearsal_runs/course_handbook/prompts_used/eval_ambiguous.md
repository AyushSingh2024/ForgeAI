---
id: eval_ambiguous
version: 1
purpose: a short question with two valid readings, answered by two different passages
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

Write ONE short, natural question that could reasonably mean the situation in passage A OR the situation in
passage B, so a good assistant should ask which one is meant, or answer both.
1. expected_behavior = "clarify".
2. key_facts: one fact from each passage (the answer for each reading).
3. quotes: one sentence copied EXACTLY from each passage.
4. notes: describe the two readings in one line.

Return JSON: {"cases": [{"question": "...", "expected_behavior": "clarify", "key_facts": [{"fact": "...", "kind": "semantic"}], "quotes": ["...", "..."], "notes": "reading 1 vs reading 2"}]}
