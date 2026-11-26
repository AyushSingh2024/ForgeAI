"""Run metadata and safe artifact paths for the web layer.

Render's free disk is ephemeral: live runs vanish on restart (the UI offers a zip download); demo runs are
committed in the repo and copied into RUNS_DIR at startup.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

from forge.util import safe_replace

ARTIFACTS = {
    "requirements": "requirements.json",
    "requirements_md": "requirements.md",
    "groundability": "groundability.json",
    "agent": "agent/agent.yaml",
    "evals": "evals/cases.jsonl",
    "evals_rejected": "evals/rejected.jsonl",
    "evals_stats": "evals/stats.json",
    "changelog": "changelog.jsonl",
    "report": "REPORT.md",
    "report_json": "report.json",
    "questions": "intake/questions.json",
    "optimize_summary": "optimize_summary.json",
    "calibration": "judge_calibration.json",
}
_RUN_ID = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


class RunStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.match(run_id):
            raise ValueError("invalid run id")
        return self.root / run_id

    def exists(self, run_id: str) -> bool:
        try:
            return (self.run_dir(run_id) / "meta.json").exists()
        except ValueError:
            return False

    def create(self, run_id: str, brief: str, mode: str, source: str = "upload") -> Path:
        d = self.run_dir(run_id)
        d.mkdir(parents=True, exist_ok=False)
        self._write(d / "meta.json", {"run_id": run_id, "created_at": time.time(), "mode": mode, "source": source,
                                      "brief": brief})
        self.set_status(run_id, status="queued")
        return d

    def meta(self, run_id: str) -> dict[str, Any]:
        return self._read(self.run_dir(run_id) / "meta.json", {})

    def status(self, run_id: str) -> dict[str, Any]:
        return self._read(self.run_dir(run_id) / "status.json", {"status": "unknown"})

    def set_status(self, run_id: str, **fields: Any) -> None:
        path = self.run_dir(run_id) / "status.json"
        cur = self._read(path, {})
        cur.update(fields, updated_at=time.time())
        self._write(path, cur)

    def list(self) -> list[dict[str, Any]]:
        out = []
        for d in self.root.iterdir():
            if not d.is_dir() or not (d / "meta.json").exists():
                continue
            meta = self._read(d / "meta.json", {})
            st = self._read(d / "status.json", {})
            rep = self._read(d / "report.json", {}) if st.get("status") in ("completed", "budget_stopped") else {}
            best = (rep.get("best") or {}).get("pass_rate")
            hold = (rep.get("holdout") or {}).get("pass_rate")
            out.append({"run_id": meta.get("run_id", d.name), "created_at": meta.get("created_at"),
                        "brief_preview": (meta.get("brief") or "")[:160], "status": st.get("status", "unknown"),
                        "source": meta.get("source", "upload"), "final_pass_rate": best, "holdout_pass_rate": hold,
                        "agent_name": rep.get("agent_name")})
        return sorted(out, key=lambda r: -(r["created_at"] or 0))

    def path_for(self, run_id: str, artifact: str) -> Path:
        rel = ARTIFACTS.get(artifact)
        if rel is None:
            raise KeyError(artifact)
        return self.run_dir(run_id) / rel

    def iteration_path(self, run_id: str, iteration: str, name: str) -> Path:
        if not re.match(r"^(\d{1,2}|final_holdout)$", iteration) or name not in ("scorecard.json", "transcripts.jsonl"):
            raise KeyError(name)
        return self.run_dir(run_id) / "iterations" / iteration / name

    def zip_run(self, run_id: str) -> bytes:
        d = self.run_dir(run_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in d.rglob("*"):
                if p.is_file() and "index" not in p.relative_to(d).parts[:2]:
                    zf.write(p, p.relative_to(d.parent))
        return buf.getvalue()

    def delete(self, run_id: str) -> None:
        shutil.rmtree(self.run_dir(run_id), ignore_errors=True)

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f"{path.suffix}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        safe_replace(tmp, path)
