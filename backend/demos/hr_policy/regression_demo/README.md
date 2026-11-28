# Regression mode demo (`forge eval --against`)

Question: would the HR agent get worse if its hosted model (`gpt-4o-mini`) were swapped for a small local one?
The agent definition, the eval cases and the baseline scorecard are the committed ones from `../run/`; only the
model answering the questions changes. Nothing here called a hosted API: the agent and the judge both ran on local
Ollama, and `FORGE_CACHE_ONLY=1` blocks any hosted call.

From `backend/`:
```
set FORGE_CACHE_ONLY=1
set LLM_PROVIDER=ollama
set AGENT_MODEL=llama3.2:3b
forge eval demos/hr_policy/run/agent/agent.yaml --cases demos/hr_policy/run/evals/cases.jsonl --split train ^
    --against demos/hr_policy/run/iterations/0/scorecard.json --out demos/hr_policy/regression_demo --fail-on-regression
```

Result ([output.txt](output.txt), [regression_diff.json](regression_diff.json), [scorecard.json](scorecard.json)):
on the 16 training cases the pass rate drops from 75% to 56%, 0 cases fixed and 3 regressed (`answ_01` cited a
quote that is not in the passage, `mult_03` missed a key fact, `must_01` answered a question it must refuse).
With `--fail-on-regression` the command exits with code 1, so it can guard a change in CI.

Caveats: the new scorecard reuses the baseline's judge-trust setting so the comparison is like for like. The
HR judge failed calibration, so here, as in the baseline, the code checks decide every verdict and the judge's
scores do not. The agent and the judge are also the same local model (`llama3.2:3b`), so treat this as a demo of
the regression mechanism, not as a fair benchmark of the two agent models.
