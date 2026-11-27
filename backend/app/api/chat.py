"""Chat with any generated agent through the generic runtime (Req 8). Rate-limited per IP."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.agents import get_runtime
from app.config import Settings, get_settings
from app.deps import get_run_store
from app.storage.runs_store import RunStore
from forge.errors import BudgetExceeded

router = APIRouter(prefix="/api/agents", tags=["chat"])
_hits: dict[str, deque] = defaultdict(deque)


class Turn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20)


def _rate_limit(ip: str, per_min: int) -> None:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_min:
        raise HTTPException(429, "too many messages, wait a minute")
    q.append(now)


@router.post("/{agent_id}/chat")
async def chat(agent_id: str, body: ChatIn, request: Request, store: RunStore = Depends(get_run_store),
               settings: Settings = Depends(get_settings)) -> dict:
    _rate_limit(request.client.host if request.client else "?", settings.chat_rate_per_min)
    rt = await run_in_threadpool(get_runtime, store, agent_id)
    try:
        ans, trace = await run_in_threadpool(rt.answer, body.message, [t.model_dump() for t in body.history[-6:]])
    except BudgetExceeded as exc:
        raise HTTPException(503, f"LLM budget exhausted: {exc}") from exc
    return {**ans.model_dump(mode="json"), "latency_ms": trace.get("latency_ms"),
            "trace": {"hits": [{k: h[k] for k in ("chunk_id", "doc_id", "page", "score", "dense", "bm25")} | {"text": h["text"][:300]}
                               for h in trace.get("hits", [])],
                      "best_score": trace.get("best_score"), "deterministic_refusal": trace.get("deterministic_refusal"),
                      "invalid_citations": trace.get("invalid_citations", [])}}
