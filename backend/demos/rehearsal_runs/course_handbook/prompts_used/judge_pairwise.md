---
id: judge_pairwise
version: 1
purpose: compare two anonymised answers to the same question (order is swapped by code on a second call)
inputs: [question, context, key_facts, answer_1, answer_2]
output_schema: PairVerdict
---
Two assistants answered the same question from the same documents. Decide which answer is better.

QUESTION: {{ question }}

CONTEXT:
{% for c in context %}
<passage>{{ c }}</passage>
{% endfor %}

KEY FACTS a correct answer must contain:
{% for f in key_facts %}
- {{ f }}
{% else %}
- (none listed)
{% endfor %}

<answer_1>
{{ answer_1 }}
</answer_1>

<answer_2>
{{ answer_2 }}
</answer_2>

Rules:
1. Prefer the answer that states more KEY FACTS correctly and invents nothing beyond the context.
2. IGNORE length, style and politeness. A longer answer is NOT better unless it has more correct key facts.
3. The order of the answers means nothing.
4. Say "tie" when they are equally good.
Write the rationale first.

Return JSON: {"rationale": "...", "winner": "1" | "2" | "tie"}
