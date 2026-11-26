"""The web layer with FastAPI's TestClient (no real model is called: builds are only queued)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("DEMOS_DIR", str(tmp_path / "no_demos"))
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("EMBEDDER", "hash")  # no model download in tests
    from app import config, deps

    config.get_settings.cache_clear()
    deps.get_run_store.cache_clear()
    deps.get_job_queue.cache_clear()
    q = deps.get_job_queue()
    monkeypatch.setattr(q, "start", lambda: None)  # do not run real builds in tests
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_build_validation(client, tiny_corpus):
    files = [("files", ("a.exe", b"MZ", "application/octet-stream"))]
    r = client.post("/api/builds", data={"brief": "short"}, files=files)
    assert r.status_code == 400
    r = client.post("/api/builds", data={"brief": "A long enough brief about the gym members."}, files=files)
    assert r.status_code == 400
    fake_pdf = [("files", ("x.pdf", b"not a pdf", "application/pdf"))]
    assert client.post("/api/builds", data={"brief": "A long enough brief about the gym members."},
                       files=fake_pdf).status_code == 400


def test_build_queued_and_listed(client, tiny_corpus):
    data = (tiny_corpus / "refund_policy.md").read_bytes()
    r = client.post("/api/builds", data={"brief": "Answer gym member questions about refunds.", "mode": "unattended"},
                    files=[("files", ("refund_policy.md", data, "text/markdown"))])
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    d = client.get(f"/api/runs/{run_id}").json()
    assert d["status"] == "queued" and [s["name"] for s in d["stages"]][0] == "ingest"
    assert client.get("/api/runs").json()[0]["run_id"] == run_id
    assert client.get(f"/api/runs/{run_id}/report").status_code == 404  # not ready yet


def test_path_traversal_and_unknown_run(client):
    assert client.get("/api/runs/..%2F..%2Fetc").status_code in (404, 422)
    assert client.get("/api/runs/does-not-exist").status_code == 404


def test_cors_header(client):
    r = client.options("/api/runs", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
