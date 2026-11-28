# Demo runs (Req 9)

Two deliberately different briefs. Every document is synthetic and describes fictional organisations, so all of it
can be committed.

| demo | documents | tools the factory should pick |
|---|---|---|
| `hr_policy/` | 5 policy PDFs (leave, travel and expenses, remote work, code of conduct, benefits) | calculator, current_date |
| `ship_spares/` | inventory CSV (300 rows), suppliers CSV, 3 supplier-terms PDFs in different layouts, maintenance notes | csv_lookup, calculator, current_date, http_weather |

## Produce the committed runs
From `backend/`, with Ollama running locally (the official runs use local models):

```
pip install -e ".[dev]"
python demos/scripts/make_hr_docs.py
python demos/scripts/make_ship_spares.py
forge build --brief demos/hr_policy/brief.txt --docs demos/hr_policy/docs --answers demos/hr_policy/answers.yaml --unattended --run-id demo_hr
forge build --brief demos/ship_spares/brief.txt --docs demos/ship_spares/docs --answers demos/ship_spares/answers.yaml --unattended --run-id demo_spares
```

Then copy each finished run folder to `demos/<name>/run/` and commit it. Copy the whole folder: requirements,
groundability, agent (with all versions), evals, iterations, changelog, llm_calls, prompts_used and REPORT.md.
At startup the API copies `demos/*/run` into `RUNS_DIR`, so the hosted site always has two finished agents.

## How the committed runs were actually made
- `hr_policy/run/`: `python demos/scripts/run_interview_demo.py hr_policy --auto` (interactive path: the pipeline
  paused on 3 questions and the script answered them from `hr_policy/answers.yaml`, standing in for a person).
- `ship_spares/run/`: `forge build ... --answers demos/ship_spares/answers.yaml --unattended`; the interviewer asked
  no questions because the brief was specific enough.
- Both: agent `openai:gpt-4o-mini`, judge local `ollama:llama3.2:3b` (see each `REPORT.md`, section 8).

## Added after the runs (the runs themselves were not re-graded)
- `*/run/judge_calibration_recheck.json`: the judge calibration re-run with the revised probes and judge prompt v2,
  same local judge (`python demos/scripts/recheck_calibration.py <run> <out.json>`). HR: 4/7 -> 6/7; ship spares 5/7 -> 5/7.
- `hr_policy/regression_demo/`: regression mode (`forge eval --against`) on the HR agent with a local model.
- The `REPORT.md` files were re-rendered with `forge report <run> --reuse-narrative` to add the "Which judge ran"
  section and the calibration explanation. Numbers and narrative are unchanged. In the three rehearsal reports the
  status now reads completed (not running) and the cost line also counts the report's own narrative call.
