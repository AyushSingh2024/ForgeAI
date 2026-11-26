"""Save uploaded files safely (sanitised names, size limit, magic-byte sniff, zip-slip protection)."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile

ALLOWED = {".pdf", ".docx", ".md", ".markdown", ".txt", ".csv", ".xlsx", ".html", ".htm"}
MAGIC = {".pdf": b"%PDF", ".docx": b"PK", ".xlsx": b"PK"}


def safe_name(name: str) -> str:
    base = PurePosixPath(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "file"
    return base[:120]


def _unique(dest_dir: Path, name: str) -> Path:
    p = dest_dir / name
    stem, suf, k = p.stem, p.suffix, 2
    while p.exists():
        p = dest_dir / f"{stem}_{k}{suf}"
        k += 1
    return p


def _check_bytes(name: str, data: bytes) -> None:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"unsupported file type: {name}")
    magic = MAGIC.get(ext)
    if magic and not data.startswith(magic):
        raise HTTPException(400, f"{name} does not look like a real {ext} file")


async def save_uploads(dest_dir: Path, files: list[UploadFile], max_mb: int) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    limit = max_mb * 1024 * 1024
    total = 0
    saved: list[Path] = []
    for f in files:
        data = await f.read(limit + 1 - total)
        total += len(data)
        if total > limit:
            raise HTTPException(413, f"uploads exceed {max_mb} MB")
        name = safe_name(f.filename or "file")
        if name.lower().endswith(".zip"):
            saved += _extract_zip(dest_dir, data, limit)
            continue
        _check_bytes(name, data)
        p = _unique(dest_dir, name)
        p.write_bytes(data)
        saved.append(p)
    if not saved:
        raise HTTPException(400, "no usable files uploaded")
    return saved


def _extract_zip(dest_dir: Path, data: bytes, limit: int) -> list[Path]:
    out = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "invalid zip file") from exc
    size = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        parts = PurePosixPath(info.filename.replace("\\", "/")).parts
        if any(p in ("..", "") for p in parts) or info.filename.startswith("/"):
            continue  # zip-slip
        name = safe_name(parts[-1])
        if Path(name).suffix.lower() not in ALLOWED or name.startswith("."):
            continue
        size += info.file_size
        if size > limit:
            raise HTTPException(413, "zip contents exceed the upload limit")
        content = zf.read(info)
        _check_bytes(name, content)
        p = _unique(dest_dir, name)
        p.write_bytes(content)
        out.append(p)
    return out


def save_brief(run_dir: Path, text: str) -> None:
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "input" / "brief.txt").write_text(text.strip(), encoding="utf-8")
