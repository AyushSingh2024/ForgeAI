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
