# ForgeAI build phases

The code was written in this order, so that something runs end to end as early as possible. Each phase has its
own tests in `backend/tests/`. Status: phases 0 to 11 are written; the tests have not been run yet (they need a
Python environment with the packages installed), and the two demo runs still have to be produced and committed.

| Phase | Name | Main folders | Done when |
|---|---|---|---|
| 0 | Setup + LLM layer | `backend/pyproject.toml`, `forge/config.py`, `forge/errors.py`, `forge/llm/*`, `prompts/` format | `pytest tests/test_llm_client.py` passes; Ollama and Groq both answer one call |
| 1 | Ingest, retrieval, runtime, tools | `forge/schemas/corpus.py`, `answer.py`, `forge/ingest/*`, `forge/retrieval/*`, `forge/runtime/*` | a hand-written `agent.yaml` answers with citations via `forge chat` |
| 2 | Intake + groundability guard (R1, R2) | `forge/intake/*`, `forge/guard/*`, schemas | at most 5 questions; requirements.md written; unsupported asks flagged |
| 3 | Agent generator (R3) | `forge/generator/*`, `schemas/agent_def.py` | `agent.yaml` generated with only the needed tools, each with a reason |
| 4 | Eval generator + validator (R4) | `forge/evals/*`, eval prompts | at least 20 validated cases, holdout split, rejected cases logged |
| 5 | Judge (R5) | `forge/judge/*`, `evals/harness.py` | scorecard_0 produced; calibration and position-swap measured |
| 6 | Critic-optimizer loop (R6) | `forge/optimizer/*` | up to 3 iterations, changes logged with before/after, regressions reverted |
| 7 | Pipeline, CLI, report (R7) | `forge/pipeline.py`, `forge/cli.py`, `forge/report/*` | `forge build --unattended` produces every artifact + REPORT.md |
| 8 | Web API | `backend/app/*` | builds, interview, artifacts and chat work through `/docs` |
| 9 | Frontend | `frontend/*` | full flow in the browser against the local API |
| 10 | Demos + docs (R9) | `backend/demos/*`, READMEs | both demo runs committed with all artifacts |
| 11 | Deploy + generality hardening | `render.yaml`, `DEPLOY.md`, CI, `backend/rehearsal/*` | live on Render + Vercel; all rehearsal briefs run unattended without crashing |
| 12 | Stretch goals | see PLAN.md section 10 | in priority order, as time allows |

R1 to R9 are the nine mandatory requirements of the assignment.
