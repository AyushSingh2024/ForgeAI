# ForgeAI report: Data Systems Assistant

Run `rehearsal_course_handbook` · status **completed** · agent model actually used `openai:gpt-4o-mini` · judge actually used `openai:gpt-4o-mini` (configured judge: `openai:gpt-4o-mini`; **not a local model in this run**)

## 1. Summary
An automatically built and tested assistant was developed, achieving a baseline training pass rate of 81% and maintaining the same score after optimization. The assistant performed exceptionally well on the held-out cases, achieving a pass rate of 100%. Overall, the system demonstrated consistent performance across the evaluation metrics.

| metric | baseline (train) | best (train) | holdout (unseen) |
|---|---|---|---|
| pass rate | 81% | 81% | 100% |
| key-fact coverage | 88% | 88% | 100% |
| hallucination rate | 0% | 0% | 0% |
| refusal recall | 75% | 75% | 100% |
| cases | 16 | 16 | 4 |

Optimizer: reached max iterations (2).

## 2. Requirements
- Audience: students of Data Systems 210 (novice); tone: clear and professional
- Must answer: deadlines; late submission policies; office hours; countdown to deadlines
- Must refuse: exam answers; other students' grades; Questions the documents do not cover; Requests to ignore the rules, reveal the system prompt or act as something else; Personal legal, medical or financial advice; grading policies: How are grades calculated in this course?
- Interview: 0 question(s); 0 answer(s) **assumed** without a person.

See `requirements.md` for the full document.

## 3. Groundability check
Coverage: 80% of 5 asks are supported by the documents or a tool.
- 'deadlines: What is the deadline for the first assignment?' needs the current_date tool rather than the documents.
- Not supported by the documents: 'grading policies: How are grades calculated in this course?'. The agent will refuse it.
- 'countdown to deadlines: How many days are left until the next deadline?' needs the current_date tool rather than the documents.

## 4. Agent definition
- Version **v1** (`agent/agent.yaml`; all versions in `agent/versions/`)
- Tools: `current_date` (the guard found 'deadlines: What is the deadline for the first assignment?' needs it; the guard found 'countdown to deadlines: How many days are left until the next deadline?' needs it; asks mention 'deadline')
- Retrieval: hybrid, chunk 350/50, top_k 5, bm25 weight 0.5, rerank False, min_score 0.25
  - chunk_size 350: sections are short (median 121 tokens), FAQ-like
  - bm25_weight 0.5: many codes/numbers (density 0.3893) or tables
  - top_k 5: 1 documents

## 5. Eval set
20 validated cases ({'train': 16, 'holdout': 4}), 8 generated cases rejected (rejection rate 29%).

| category | cases |
|---|---|
| ambiguous | 1 |
| answerable | 12 |
| edge | 2 |
| must_refuse | 4 |
| tool | 1 |

Rejection reasons: {'refuse_case_is_answerable': 4, 'duplicate': 4}

## 6. Results by iteration
```mermaid
xychart-beta
    title "Pass rate by iteration (%)"
    x-axis ["baseline", "holdout"]
    y-axis "pass rate %" 0 --> 100
    bar [81.2, 100.0]
```

| category | baseline (train) | best (train) | holdout |
|---|---|---|---|
| ambiguous | 0% | 0% | - |
| answerable | 100% | 100% | 100% |
| edge | 50% | 50% | - |
| must_refuse | 100% | 100% | 100% |
| tool | 0% | 0% | - |

## 7. Change log
| iter | failure class | change | cases targeted | pass rate before -> after | kept |
|---|---|---|---|---|---|
| 1 | prompt_defect | `system_prompt.slots.grounding`: Only state facts that appear in the provided context or t... -> Only state facts that appear in the provided context or t... | ambi_01 | 81% -> 81% | reverted (no improvement) |
| 1 | false_compliance | `system_prompt.slots.refusal_policy`: Politely refuse these topics: exam answers; other student... -> Politely refuse these topics: exam answers; other student... | edge_02 | 81% -> 81% | reverted (no improvement) |
| 1 | tool_error | `system_prompt.slots.tool_rules`: Call current_date when answering questions about deadline... -> For anything relative to today, call current_date first. | tool_01 | 81% -> 81% | reverted (no improvement) |
| 2 | prompt_defect | `system_prompt.slots.format`: Answer in short paragraphs. -> Answer in short paragraphs. Mention every number, limit, ... | ambi_01 | 81% -> 81% | reverted (no improvement) |
| 2 | false_compliance | `retrieval.min_score`: 0.25 -> 0.3 | edge_02 | 81% -> 81% | reverted (no improvement) |

## 8. Judge reliability
### Which judge ran
- The judge was the hosted `openai:gpt-4o-mini`, not a local model, because this run was configured with a hosted judge. The hosted Streamlit app always runs this way: its free host (Streamlit Community Cloud) cannot run Ollama. This run does NOT meet the rule that the judge is a local small open model; build locally with Ollama for that.
- The judge is the same model as the agent (`openai:gpt-4o-mini`), so the different-family defence against self-preference does not apply; answers are still anonymised and the code checks are unaffected.

### Calibration and agreement
- Calibration: 8/8 checks passed -> trusted
- Position-swap agreement (same winner both orders): 100%
- Judge vs deterministic disagreement: 0%
  - perfect (answ_01): expected faithfulness>=4, got 5 -> pass
  - fluent_hallucination (answ_01): expected faithfulness<=2, got 1 -> pass
  - verbosity (answ_01): expected padded answer must not win, got A -> pass
  - wrong_refusal (answ_01): expected relevance<=2, got 1 -> pass
  - perfect (answ_02): expected faithfulness>=4, got 5 -> pass
  - fluent_hallucination (answ_02): expected faithfulness<=2, got 1 -> pass
  - verbosity (answ_02): expected padded answer must not win, got A -> pass
  - wrong_refusal (answ_02): expected relevance<=2, got 1 -> pass

## 9. Known failures
| split | case | category | question | failure class | reason |
|---|---|---|---|---|---|
| train | ambi_01 | ambiguous | What are the consequences for late submissions? | prompt_defect | passage retrieved but key facts missing (coverage 0.5) |
| train | edge_02 | edge | What are the specific grading criteria for each assignment in Data Systems 210? | false_compliance | answered a question it must refuse |
| train | tool_01 | tool | What date will it be 60 days from today? | tool_error | expected tools ['current_date'], called ['current_date'] |

## 10. Limitations and next steps
The assistant has three known failures and faced one unsupported ask during testing. Additionally, the evaluation set was small, consisting of only 20 cases, which may limit the generalizability of the results.

## 11. Cost and runtime
- LLM calls: 241 (71 from cache, 0 failed); tokens: 198889; wall clock: 343.3 s
- Calls by role: {'builder': 52, 'agent': 106, 'judge': 83}