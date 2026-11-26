---
id: eval_answerable
version: 1
purpose: one realistic question answerable from a single passage, with key facts and an exact quote
inputs: [audience, chunk, n]
output_schema: CaseDraftList
---
You write test questions for a document assistant used by: {{ audience }}.

<passage>
{{ chunk }}
</passage>

Write {{ n }} question(s) a real user would ask that this passage fully answers.
1. Paraphrase: do NOT copy sentences from the passage into the question.
2. key_facts: 1 to 3 short atomic statements the correct answer MUST contain (include exact numbers, names, limits).
   kind = "numeric" if the fact contains a number, otherwise "semantic".
3. quotes: the sentence(s) that contain the answer, copied EXACTLY character for character from the passage.
4. expected_behavior: "answer".
{% if avoid %}
5. These questions already exist. Ask about a DIFFERENT fact in the passage; do not repeat or rephrase them:
{% for q in avoid %}
   - {{ q }}
{% endfor %}
{% endif %}

Return JSON: {"cases": [{"question": "...", "expected_behavior": "answer", "key_facts": [{"fact": "...", "kind": "numeric"}], "quotes": ["exact sentence"], "notes": ""}]}
