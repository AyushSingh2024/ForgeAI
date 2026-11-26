# ForgeAI backend

Python 3.11+ and FastAPI. It hosts the ForgeAI factory: a brief and a folder of documents go in, and a tested,
self-improved, declaratively defined agent comes out, together with an honest report. The same pipeline runs from
the `forge` CLI and from the REST API (deployed on Render).

## Setup (local, fully offline)
```
python -m venv .venv
.venv\Scripts\activate            (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
copy .env.example .env            (then edit it if needed)
ollama pull qwen2.5:7b-instruct
ollama pull gemma2:9b
forge doctor
```

## Run the factory
```
forge build --brief demos/hr_policy/brief.txt --docs demos/hr_policy/docs --unattended
forge chat runs/<run_id>/agent/agent.yaml
```
**Unseen brief at review:** `forge build --brief path/to/brief.txt --docs path/to/docs --unattended`.
Everything lands in `runs/<run_id>/`. Start with `REPORT.md`.

## Run the API
```
uvicorn app.main:app --reload       (Swagger at http://localhost:8000/docs)
```

## Tests
```
pytest -m "not slow"
```
The tests use a scripted fake model and a hashing embedder, so they need no GPU, no network and no model download.

## Layout
- `forge/`: the engine. It has no web code and never imports `app/`.
  - `llm/`: the only code that talks to a model. Provider switch (ollama / groq / hf), JSON repair, cache, budget.
  - `ingest/`, `retrieval/`: loaders with page provenance, chunker, hybrid BM25 + dense search.
  - `intake/` (R1), `guard/` (R2), `generator/` (R3), `evals/` (R4), `judge/` (R5), `optimizer/` (R6), `report/` (R7), `runtime/` (R8).
  - `pipeline.py`: wires the stages together; resumable through `.stages/*.done` markers.
- `app/`: the web layer (routes, background job queue, storage).
- `prompts/`: every prompt, versioned. Each run also snapshots the prompts it used into `runs/<id>/prompts_used/`.
- `demos/` (R9), `rehearsal/` (generality), `tests/`.

## Provider switch
`LLM_PROVIDER=ollama` (default, local) or `groq` / `hf` (hosted, used on Render, which has no GPU).
`JUDGE_MODEL` should be a different model family from `AGENT_MODEL`; `forge doctor` warns if it isn't.
