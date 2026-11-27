---
id: report_narrative
version: 2
purpose: two short honest paragraphs for REPORT.md, written only from the given numbers
inputs: [facts]
output_schema: Narrative
---
Write two short paragraphs for an engineering report about an automatically built and tested assistant.

FACTS (the only numbers you may use):
{{ facts | tojson }}

1. "summary": 3 or 4 sentences: what was built, how it scored before and after optimisation, and how it did on
   the held-out cases.
2. "limitations": 2 or 3 sentences naming the weaknesses plainly (known failures, small eval set, a judge that
   failed calibration if so, anything in notes).
Use ONLY numbers that appear in FACTS (code checks this). Do not exaggerate. Do not invent results. Do not use praise or intensity words (significant, exceptional,
strong, excellent, robust). State changes as plain "from X% to Y%". Whenever you give the held-out score, give the
number of held-out cases too and say it is too few to generalise from if it is under 10.

Return JSON: {"summary": "...", "limitations": "..."}
