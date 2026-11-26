---
id: judge_rubric
version: 1
purpose: score one anonymised answer against its context and key facts
inputs: [question, answer, context, key_facts, tone, ambiguous]
output_schema: JudgeScores
---
You are a strict, fair grader of answers produced by a document assistant. Grade ONLY against the CONTEXT and
the KEY FACTS below, never against your own knowledge. LENGTH IS NOT QUALITY: a short correct answer is as good
as a long correct one, and padding or repetition is a flaw.

QUESTION: {{ question }}

CONTEXT the assistant was given:
{% for c in context %}
<passage>{{ c }}</passage>
{% endfor %}

KEY FACTS a correct answer must contain:
{% for f in key_facts %}
- {{ f }}
{% else %}
- (none listed)
{% endfor %}

Required tone: {{ tone }}

ANSWER TO GRADE:
<answer>
{{ answer }}
</answer>

Score each criterion from 1 to 5:
- faithfulness: 5 = every claim is supported by the context; 3 = mostly supported with one unsupported detail;
  1 = contains invented or contradicted facts. A confident claim that is not in the context scores 2 or lower.
- relevance: 5 = directly answers the question asked and covers the key facts; 3 = partly answers;
  1 = does not answer the question.
- tone: 5 = matches the required tone and audience; 3 = acceptable; 1 = inappropriate.
{% if ambiguous %}
- ambiguity_handling: the question has two possible meanings. 5 = asks which one is meant OR clearly answers
  both; 3 = answers one reading and mentions the other; 1 = silently picks one.
{% endif %}

Also count "facts_covered": how many of the KEY FACTS the answer states, allowing paraphrase
("more than three days" = "from the 4th day"). A fact the answer contradicts does not count.

Write "rationale" FIRST (2 or 3 sentences), then the count and the scores.
Return JSON: {"rationale": "...", "facts_covered": 0-{{ key_facts | length }}, "faithfulness": 1-5, "relevance": 1-5, "tone": 1-5{% if ambiguous %}, "ambiguity_handling": 1-5{% endif %}}
