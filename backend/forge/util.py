"""Small shared helpers: file IO, text normalisation, number parsing, quote matching."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from rapidfuzz import fuzz

T = TypeVar("T", bound=BaseModel)

# ------------------------------------------------------------------ files

def safe_replace(tmp: str | Path, dest: str | Path, attempts: int = 20) -> None:
    """os.replace with retries: on Windows a reader (the API polling status.json, OneDrive sync, antivirus)
    can briefly lock the destination and make the rename fail with PermissionError."""
    import time

    for i in range(attempts):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.05 * (i + 1))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    safe_replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_model(path: Path, cls: type[T]) -> T:
    return cls.model_validate(read_json(path))


def write_jsonl(path: Path, items: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for it in items:
            if isinstance(it, BaseModel):
                it = it.model_dump(mode="json")
            fh.write(json.dumps(it, ensure_ascii=False, default=str) + "\n")


def append_jsonl(path: Path, item: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(item, BaseModel):
        item = item.model_dump(mode="json")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: Path, cls: type[T] | None = None) -> list[Any]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            out.append(cls.model_validate(obj) if cls else obj)
    return out


# ------------------------------------------------------------------ text

def slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return (text or "doc")[:max_len]


def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_WS = re.compile(r"\s+")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                         " ": " "})


def normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").translate(_QUOTES)).strip().lower()


def quote_in_text(quote: str, text: str, fuzzy_threshold: int = 92) -> bool:
    """True if quote appears verbatim (after normalisation) in text, or nearly so (fuzzy partial match)."""
    q, t = normalize(quote), normalize(text)
    if not q or len(q) < 4:
        return False
    if q in t:
        return True
    if len(q) > len(t) + 10:
        return False
    return fuzz.partial_ratio(q, t) >= fuzzy_threshold


def find_span(quote: str, text: str, threshold: int = 90) -> str | None:
    """Return the exact span of `text` that best matches `quote` (used to repair near-miss quotes)."""
    if not quote or not text:
        return None
    if quote in text:
        return quote
    res = fuzz.partial_ratio_alignment(quote, text)
    if res is None or res.score < threshold:
        return None
    return text[res.dest_start:res.dest_end]


# ------------------------------------------------------------------ numbers

_NUM = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?(?:\s?[kK]\b)?%?")


def parse_numbers(text: str) -> list[float]:
    """Extract numbers, normalising '1,200' / '1200' / '1.2k' / '15%'."""
    out = []
    for m in _NUM.findall(text or ""):
        s = m.strip().rstrip("%").replace(",", "").strip()
        mult = 1.0
        if s.lower().endswith("k"):
            mult, s = 1000.0, s[:-1].strip()
        try:
            out.append(float(s) * mult)
        except ValueError:
            continue
    return out


def number_in(value: float, numbers: Iterable[float], rel_tol: float = 0.005) -> bool:
    for n in numbers:
        if value == n or (value != 0 and abs(value - n) / abs(value) <= rel_tol):
            return True
    return False
