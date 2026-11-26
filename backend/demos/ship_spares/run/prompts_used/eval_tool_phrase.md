---
id: eval_tool_phrase
version: 1
purpose: phrase a code-computed data query as a natural user question
inputs: [query, audience]
output_schema: PhrasedQuestion
---
A user ({{ audience }}) wants this information from a data table: {{ query }}

Write the question they would type, in natural words. Do NOT include the answer. Keep exact values (codes,
names) as they are.

Return JSON: {"question": "..."}
