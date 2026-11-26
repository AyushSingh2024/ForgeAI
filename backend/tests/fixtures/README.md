# Test fixtures

- `tiny_corpus/`: three short documents for a fictional gym plus `classes.csv`. This is deliberately not one of
  the demo domains, which keeps the tests honest about generality.
- `handwritten_agent.yaml`: an agent definition written by hand for `tiny_corpus` (used by the Req 8 runtime test).
- The tests use the `hash` embedder (no model download) and scripted fake LLM providers (see `conftest.py`),
  so `pytest -m "not slow"` runs fully offline.
