---
id: guard_probe
version: 2
purpose: realistic user questions that test whether one ask can be answered from reference documents
inputs: [ask]
output_schema: ProbeList
---
Write 2 realistic questions a user would ask about: "{{ ask }}"

Rules:
1. The questions must be answerable from general reference documents (policies, manuals, price lists, tables).
   Do NOT ask about the user's personal situation or data (their own balance, their own dates).
2. Do NOT invent specifics that are not in the ask: no city, country, year, product or person names.
3. Vary the wording. One question may ask for a number, limit or condition.

Return JSON: {"probes": ["question 1", "question 2"]}
