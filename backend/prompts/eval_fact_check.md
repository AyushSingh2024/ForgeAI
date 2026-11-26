---
id: eval_fact_check
version: 1
purpose: does this text state or directly imply this fact?
inputs: [text, fact]
output_schema: FactCheck
---
<text>
{{ text }}
</text>

Fact: "{{ fact }}"

Is the fact stated in, or directly implied by, the text? Use no outside knowledge. Write one sentence of
reasoning first.

Return JSON: {"reasoning": "...", "entailed": true}
