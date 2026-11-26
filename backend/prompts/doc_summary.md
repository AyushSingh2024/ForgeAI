---
id: doc_summary
version: 1
purpose: one or two sentence summary of a document for the corpus profile
inputs: [title, text]
output_schema: Summary
---
Summarise what this document is and which topics it covers, in at most 2 sentences. Be factual. No opinions.

<document title="{{ title }}">
{{ text }}
</document>

Return JSON: {"summary": "..."}
