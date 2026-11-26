"""Serve the files a run produced (tabs in the UI, downloads). Paths come only from a whitelist."""

from __future__ import annotations

import json

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response

from app.deps import get_run_or_404, get_run_store
from app.storage.runs_store import RunStore

router = APIRouter(prefix="/api/runs/{run_id}", tags=["artifacts"])


def _read(store: RunStore, run_id: str, name: str):
    try:
        p = store.path_for(run_id, name)
    except KeyError as exc:
        raise HTTPException(404, "unknown artifact") from exc
    if not p.exists():
        raise HTTPException(404, f"{name} is not available yet")
    return p


def _jsonl(text: str) -> list:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@router.get("/requirements")
def requirements(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    p = _read(store, run_id, "requirements")
    md = store.path_for(run_id, "requirements_md")
    return {"data": json.loads(p.read_text(encoding="utf-8")),
            "markdown": md.read_text(encoding="utf-8") if md.exists() else ""}


@router.get("/groundability")
def groundability(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    return json.loads(_read(store, run_id, "groundability").read_text(encoding="utf-8"))


@router.get("/agent")
def agent(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    p = _read(store, run_id, "agent")
    text = p.read_text(encoding="utf-8")
    versions = sorted((p.parent / "versions").glob("agent_v*.yaml"), key=lambda x: int(x.stem.split("_v")[1]))
    return {"data": yaml.safe_load(text), "yaml": text,
            "versions": [{"version": int(v.stem.split("_v")[1]), "data": yaml.safe_load(v.read_text(encoding="utf-8"))}
                         for v in versions]}


@router.get("/evals")
def evals(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    cases = _jsonl(_read(store, run_id, "evals").read_text(encoding="utf-8"))
    rej = store.path_for(run_id, "evals_rejected")
    stats = store.path_for(run_id, "evals_stats")
    return {"cases": cases, "rejected": _jsonl(rej.read_text(encoding="utf-8")) if rej.exists() else [],
            "stats": json.loads(stats.read_text(encoding="utf-8")) if stats.exists() else {}}


@router.get("/scorecards")
def scorecards(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    out = []
    for it in [str(i) for i in range(0, 10)] + ["final_holdout"]:
        p = store.iteration_path(run_id, it, "scorecard.json")
        if p.exists():
            sc = json.loads(p.read_text(encoding="utf-8"))
            out.append({"iteration": it, **sc})
    return {"scorecards": out}


@router.get("/scorecards/{iteration}/cases/{case_id}")
def case_transcript(iteration: str, case_id: str, run_id: str = Depends(get_run_or_404),
                    store: RunStore = Depends(get_run_store)) -> dict:
    try:
        sc_p = store.iteration_path(run_id, iteration, "scorecard.json")
        tr_p = store.iteration_path(run_id, iteration, "transcripts.jsonl")
    except KeyError as exc:
        raise HTTPException(404, "unknown iteration") from exc
    if not sc_p.exists() or not tr_p.exists():
        raise HTTPException(404, "iteration not available")
    result = next((c for c in json.loads(sc_p.read_text(encoding="utf-8"))["cases"] if c["case_id"] == case_id), None)
    transcript = next((t for t in _jsonl(tr_p.read_text(encoding="utf-8")) if t["case_id"] == case_id), None)
    cases_p = store.path_for(run_id, "evals")
    case = next((c for c in _jsonl(cases_p.read_text(encoding="utf-8")) if c["id"] == case_id), None) \
        if cases_p.exists() else None
    if result is None or transcript is None:
        raise HTTPException(404, "case not found in this iteration")
    return {"case": case, "result": result, "transcript": transcript}


@router.get("/changelog")
def changelog(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    p = store.path_for(run_id, "changelog")
    summary = store.path_for(run_id, "optimize_summary")
    return {"entries": _jsonl(p.read_text(encoding="utf-8")) if p.exists() else [],
            "summary": json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else None}


@router.get("/report", response_class=PlainTextResponse)
def report(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> str:
    return _read(store, run_id, "report").read_text(encoding="utf-8")


@router.get("/report.json")
def report_json(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> dict:
    return json.loads(_read(store, run_id, "report_json").read_text(encoding="utf-8"))


@router.get("/download")
def download(run_id: str = Depends(get_run_or_404), store: RunStore = Depends(get_run_store)) -> Response:
    return Response(store.zip_run(run_id), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="forgeai-{run_id}.zip"'})
