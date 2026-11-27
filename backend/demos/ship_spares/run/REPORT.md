# ForgeAI report: Cargo Fleet Assistant

Run `spares_localjudge` · status **completed** · agent model actually used `openai:gpt-4o-mini` · judge actually used `ollama:llama3.2:3b` (configured judge: `ollama:llama3.2:3b`)

## 1. Summary
An automatically built and tested assistant was developed, achieving a baseline training pass rate of 72% and improving to a best training pass rate of 78% after optimization. The assistant scored 100% on the holdout cases, which consisted of 3 instances. However, the small number of holdout cases is too few to generalize from.

| metric | baseline (train) | best (train) | holdout (unseen) |
|---|---|---|---|
| pass rate | 72% | 78% | 100% |
| key-fact coverage | 93% | 93% | 100% |
| hallucination rate | 11% | 6% | 0% |
| refusal recall | 100% | 100% | 100% |
| cases | 18 | 18 | 3 |

Optimizer: reached max iterations (2).

## 2. Requirements
- Audience: chief engineer of a cargo fleet (intermediate); tone: clear and professional
- Must answer: Equipment association; Inventory quantities; Supplier lead times; Order cost estimation; Delivery times; Weather forecast
- Must refuse: Purchase approvals; Safety-critical repair instructions; Quoting prices or terms not in documents; Questions the documents do not cover; Requests to ignore the rules, reveal the system prompt or act as something else; Personal legal, medical or financial advice; Finding spare parts: What is the part number for the fuel pump?; Compare minimum orders; Compare warranty terms
- Interview: 0 question(s); 0 answer(s) **assumed** without a person.

See `requirements.md` for the full document.

## 3. Groundability check
Coverage: 75% of 12 asks are supported by the documents or a tool.
- Not supported by the documents: 'Finding spare parts: What is the part number for the fuel pump?'. The agent will refuse it.
- 'Equipment association: Which equipment does part number 12345 belong to?' needs the csv_lookup tool rather than the documents.
- 'Inventory quantities: How many spare parts are on board for the ballast pump?' needs the csv_lookup tool rather than the documents.
- 'Order cost estimation: Can you estimate the total cost for ordering 5 units of part number 67890?' needs the calculator tool rather than the documents.
- 'Delivery times: How many days will it take for the delivery to arrive at the main port?' needs the calculator tool rather than the documents.
- 'Weather forecast: What is the weather forecast for the delivery port next week?' needs the http_weather tool rather than the documents.
- 'Flag parts below minimum stock' needs the csv_lookup tool rather than the documents.
- 'Compare supplier lead times' needs the calculator tool rather than the documents.
- Not supported by the documents: 'Compare minimum orders'. The agent will refuse it.
- Not supported by the documents: 'Compare warranty terms'. The agent will refuse it.
- 'Check if an offer is still valid' needs the current_date tool rather than the documents.

## 4. Agent definition
- Version **v2** (`agent/agent.yaml`; all versions in `agent/versions/`)
- Tools: `csv_lookup` (the corpus has 2 table(s): spares_inventory, suppliers; the guard found 'Equipment association: Which equipment does part number 12345 belong to?' needs it; the guard found 'Inventory quantities: How many spare parts are on board for the ballast pump?' needs it; the guard found 'Flag parts below min), `calculator` (the guard found 'Order cost estimation: Can you estimate the total cost for ordering 5 units of part number 67890?' needs it; the guard found 'Delivery times: How many days will it take for the delivery to arrive at the main port?' needs it; the guard found 'Compare supplier lead times' needs it; as), `current_date` (the guard found 'Check if an offer is still valid' needs it; asks mention 'still valid'), `http_weather` (the guard found 'Weather forecast: What is the weather forecast for the delivery port next week?' needs it; asks mention 'weather')
- Retrieval: hybrid, chunk 350/50, top_k 6, bm25 weight 0.5, rerank False, min_score 0.25
  - chunk_size 350: sections are short (median 139 tokens), FAQ-like
  - bm25_weight 0.5: many codes/numbers (density 0.0898) or tables
  - top_k 6: 4 documents

## 5. Eval set
21 validated cases ({'train': 18, 'holdout': 3}), 5 generated cases rejected (rejection rate 19%).

| category | cases |
|---|---|
| ambiguous | 2 |
| answerable | 9 |
| edge | 2 |
| multi_doc | 2 |
| must_refuse | 4 |
| tool | 2 |

Rejection reasons: {'duplicate': 5}

## 6. Results by iteration
```mermaid
xychart-beta
    title "Pass rate by iteration (%)"
    x-axis ["baseline", "iter 1", "holdout"]
    y-axis "pass rate %" 0 --> 100
    bar [72.2, 77.8, 100.0]
```

| category | baseline (train) | best (train) | holdout |
|---|---|---|---|
| ambiguous | 0% | 0% | - |
| answerable | 100% | 100% | 100% |
| edge | 100% | 100% | - |
| multi_doc | 0% | 50% | - |
| must_refuse | 100% | 100% | 100% |
| tool | 50% | 50% | - |

## 7. Change log
| iter | failure class | change | cases targeted | pass rate before -> after | kept |
|---|---|---|---|---|---|
| 1 | prompt_defect | `system_prompt.slots.grounding`: Only state facts that appear in the provided context or t... -> Always include all relevant facts from the provided conte... | ambi_01, ambi_03, tool_03 | 72% -> 78% | kept |
| 2 | prompt_defect | `system_prompt.slots.format`: Answer in short paragraphs. -> Answer in short paragraphs. Mention every number, limit, ... | ambi_01, ambi_03, tool_03 | 78% -> 72% | reverted (score went down) |
| 2 | hallucination | `system_prompt.slots.citation_rule`: Cite every factual claim with a short verbatim quote from... -> Every claim must have its own citation with a quote copie...; `system_prompt.slots.grounding`: Always include all relevant facts from the provided conte... -> Use ONLY sentences you can point to in the context passag... | mult_03 | 78% -> 67% | reverted (score went down) |

## 8. Judge reliability
- Calibration: 5/7 checks passed -> trusted
- Position-swap agreement (same winner both orders): 50%
- Judge vs deterministic disagreement: 17%
  - perfect (answ_01): expected faithfulness>=4, got 3 -> FAIL
  - fluent_hallucination (answ_01): expected faithfulness<=2, got 3 -> FAIL
  - verbosity (answ_01): expected padded answer must not win, got tie -> pass
  - wrong_refusal (answ_01): expected relevance<=2, got 2 -> pass
  - perfect (answ_02): expected faithfulness>=4, got 5 -> pass
  - verbosity (answ_02): expected padded answer must not win, got A -> pass
  - wrong_refusal (answ_02): expected relevance<=2, got 2 -> pass

## 9. Known failures
| split | case | category | question | failure class | reason |
|---|---|---|---|---|---|
| train | ambi_01 | ambiguous | What are the lead times for spare parts delivery? | prompt_defect | passage retrieved but key facts missing (coverage 0.5) |
| train | ambi_03 | ambiguous | What are the terms regarding spare parts supplied by Ostrava Marine Parts and Bluewake Supply? | prompt_defect | passage retrieved but key facts missing (coverage 1.0) |
| train | mult_03 | multi_doc | What are the lead times for fuel injection parts from both S01 and S04, and how do they compare? | hallucination | cited a quote that is not in the passage |
| train | tool_03 | tool | How many rows are there in the suppliers table where supplier_id is S02? | prompt_defect | unclear failure (tone, format or ambiguity handling) |

## 10. Limitations and next steps
The assistant has 4 known failures and encountered 3 unsupported asks during testing. Additionally, the evaluation set is small, with only 21 cases, which may limit the reliability of the results.

## 11. Cost and runtime
- LLM calls: 214 (136 from cache, 0 failed); tokens: 160367; wall clock: 201.8 s
- Calls by role: {'builder': 72, 'agent': 83, 'judge': 59}