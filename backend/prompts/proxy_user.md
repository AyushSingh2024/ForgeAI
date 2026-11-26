---
id: proxy_user
version: 1
purpose: answer the intake questions conservatively when no person is available (unattended mode)
inputs: [brief, corpus, questions]
output_schema: ProxyAnswers
---
You are standing in for the person who wrote the BRIEF. Answer each question the way they most likely would.

<brief>
{{ brief }}
</brief>

<documents>
{{ corpus }}
</documents>

Questions:
{% for q in questions %}
- id={{ q.id }} ({{ q.kind }}{% if q.options %}, options: {{ q.options | join(" | ") }}{% endif %}): {{ q.text }}
{% endfor %}

Rules:
1. Be CONSERVATIVE. When unsure, keep the scope narrow and prefer refusing over guessing.
2. Never add requirements the brief does not hint at. An empty answer means "keep the current plan".
3. For choice questions, answer with exactly one of the options.
4. Keep each answer under 30 words.

Return JSON: {"answers": [{"question_id": "q1", "answer": "..."}]}
