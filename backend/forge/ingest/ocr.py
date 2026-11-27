"""OCR for scanned PDF pages and image files, using RapidOCR (pip-only ONNX models, runs offline on CPU).

If the package is missing or fails to load, OCR is simply unavailable: the caller records a warning and skips the
page, exactly as before. OCR never stops a run.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

log = logging.getLogger(__name__)
MAX_OCR_PAGES = 60  # per run; about 2 to 4 s per page on a laptop CPU
_pages_done = 0


@lru_cache(maxsize=1)
def _engine():
    try:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()
    except Exception as exc:  # noqa: BLE001
        log.warning("OCR unavailable (%s); scanned pages will be skipped", exc)
        return None


def available() -> bool:
    return _engine() is not None


def budget_left() -> bool:
    return _pages_done < MAX_OCR_PAGES


def ocr_array(img: np.ndarray) -> str:
    """Text of an RGB/RGBA/gray image array, in reading order (top to bottom, left to right)."""
    global _pages_done
    eng = _engine()
    if eng is None:
        return ""
    if img.ndim == 3 and img.shape[2] == 4:
        img = img[:, :, :3]
    try:
        result, _ = eng(img)
    except Exception as exc:  # noqa: BLE001
        log.warning("OCR failed on one image: %s", exc)
        return ""
    _pages_done += 1
    if not result:
        return ""
    items = []
    for box, text, score in result:
        if float(score) < 0.5 or not str(text).strip():
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), max(ys), min(xs), str(text).strip()))
    items.sort(key=lambda it: (it[0], it[2]))
    lines: list[list[tuple[float, str]]] = []
    last_mid = None
    for top, bottom, left, text in items:
        mid = (top + bottom) / 2
        height = max(1.0, bottom - top)
        if last_mid is not None and abs(mid - last_mid) < height * 0.6:
            lines[-1].append((left, text))
        else:
            lines.append([(left, text)])
            last_mid = mid
    return "\n".join(" ".join(t for _, t in sorted(line)) for line in lines)


def ocr_pdf_page(page, dpi: int = 200) -> str:
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return ocr_array(img)


def ocr_image_file(path) -> str:
    import fitz  # pymupdf can open common image formats directly

    with fitz.open(str(path)) as doc:
        return "\n\n".join(ocr_pdf_page(p, dpi=150) for p in doc)
