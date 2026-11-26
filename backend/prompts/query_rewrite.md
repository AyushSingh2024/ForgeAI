---
id: query_rewrite
version: 1
purpose: multi-query retrieval; two alternative phrasings of a user question
inputs: [query]
output_schema: Rewrites
---
Rewrite the user question below in two different ways that would help a search engine find the answer in a
set of documents. Keep every name, number and code exactly. Do not answer the question.

Question: {{ query }}

Return JSON: {"queries": ["first rewrite", "second rewrite"]}
