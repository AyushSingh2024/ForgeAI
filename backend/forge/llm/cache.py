"""SQLite disk cache for LLM responses: cheap, reproducible reruns. FORGE_NO_CACHE=1 disables it."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class LLMCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, response TEXT, created_at REAL)")
        self._conn.commit()

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT response FROM calls WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, response: str) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO calls VALUES (?, ?, ?)", (key, response, time.time()))
            self._conn.commit()


class NullCache:
    def get(self, key: str) -> None:
        return None

    def put(self, key: str, response: str) -> None:
        return None
