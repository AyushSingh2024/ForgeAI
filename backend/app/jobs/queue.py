"""A tiny in-process job queue: one worker thread (Render free has little RAM), plus an interview watchdog."""

from __future__ import annotations

import logging
import queue
import threading
import time

from app.jobs.worker import run_job
from app.storage.runs_store import RunStore

log = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, store: RunStore, interview_timeout_min: int = 30, concurrency: int = 1):
        self.store = store
        self.timeout_s = interview_timeout_min * 60
        self._q: queue.Queue[tuple[str, str]] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self.concurrency = concurrency
        self.active: set[str] = set()

    # ------------------------------------------------------------------ api
    def submit(self, run_id: str, mode: str) -> None:
        self.store.set_status(run_id, status="queued")
        self._q.put((run_id, mode))

    def resume(self, run_id: str) -> None:
        mode = self.store.meta(run_id).get("mode", "unattended")
        self.submit(run_id, mode)

    def cancel(self, run_id: str) -> None:
        (self.store.run_dir(run_id) / "CANCEL").write_text("cancel", encoding="utf-8")
        if run_id not in self.active:
            self.store.set_status(run_id, status="cancelled")

    def position(self, run_id: str) -> int | None:
        items = list(self._q.queue)
        for i, (rid, _) in enumerate(items):
            if rid == run_id:
                return i + 1
        return None

    # -------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.recover()
        for i in range(self.concurrency):
            t = threading.Thread(target=self._loop, name=f"forge-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        threading.Thread(target=self._watchdog, name="forge-watchdog", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def recover(self) -> None:
        """After a restart (Render sleeps/redeploys), re-queue runs that were queued or running."""
        for r in self.store.list():
            if r["status"] in ("queued", "running"):
                log.info("re-queueing interrupted run %s", r["run_id"])
                self.resume(r["run_id"])

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_id, mode = self._q.get(timeout=1)
            except queue.Empty:
                continue
            self.active.add(run_id)
            try:
                run_job(self.store, run_id, mode)
            finally:
                self.active.discard(run_id)
                self._q.task_done()

    def _watchdog(self) -> None:
        """Auto-skip interviews nobody answered, so a run never hangs forever."""
        while not self._stop.is_set():
            time.sleep(30)
            for r in self.store.list():
                if r["status"] != "awaiting_answers":
                    continue
                st = self.store.status(r["run_id"])
                if time.time() - float(st.get("updated_at", time.time())) > self.timeout_s:
                    d = self.store.run_dir(r["run_id"])
                    (d / "intake").mkdir(exist_ok=True)
                    (d / "intake" / "answers.json").write_text('{"__skip__": true}', encoding="utf-8")
                    log.info("interview timeout: auto-skipping %s", r["run_id"])
                    self.resume(r["run_id"])
