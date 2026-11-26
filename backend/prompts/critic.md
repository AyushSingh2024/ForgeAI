---
id: critic
version: 1
purpose: classify a failure the rules could not classify, with a one-line hypothesis
inputs: [question, expected, key_facts, answer, checks, judge]
output_schema: CriticVerdict
---
A document assistant failed a test case. Classify WHY, choosing exactly one class:
- retrieval_miss: the right passage was not found.
- prompt_defect: the passage was found but the answer missed facts, had the wrong format/tone, or handled ambiguity badly.
- hallucination: the answer states things that are not in the passages.
- wrong_refusal: it refused a question it should have answered.
- false_compliance: it answered a question it should have refused.
- tool_error: it did not use, or misused, a tool it needed.

Question: {{ question }}
Expected behaviour: {{ expected }}
Key facts: {{ key_facts | join("; ") }}
Answer: {{ answer }}
Automatic checks: {{ checks | tojson }}
Judge: {{ judge | tojson }}

Write the reasoning first. The hypothesis is one sentence about what to change.
Return JSON: {"reasoning": "...", "failure_class": "...", "hypothesis": "..."}
