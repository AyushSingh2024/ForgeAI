---
id: intake_draft
version: 1
purpose: draft the requirements of the agent from the brief and the list of documents
inputs: [brief, corpus]
output_schema: RequirementsDraft
---
You are designing a question-answering assistant. Read the BRIEF and the list of DOCUMENTS it will use, then
write its requirements.

<brief>
{{ brief }}
</brief>

<documents>
{{ corpus }}
</documents>

Rules:
1. Use ONLY what the brief says or clearly implies. Do not invent features.
2. must_answer: 3 to 8 topics users will ask about that the documents seem to cover. Give a realistic example question for each.
3. must_refuse: topics the brief says to avoid, plus anything clearly risky for this audience. Give a short reason.
4. scope.in_scope / scope.out_of_scope: short phrases.
5. audience.who: who will use it. audience.expertise: novice, intermediate or expert.
6. tone.style: a few words. tone.formality: low, medium or high.
7. output_preferences.format: prose, bullets or table. max_words between 80 and 300.
8. agent_name: a short descriptive name (2 to 4 words).
9. confidence: for each field, 0.0 to 1.0, where 1.0 = the brief states it explicitly and 0.0 = a pure guess.

Return ONLY the JSON object. Rule 1 again: do not invent requirements the brief does not support.
