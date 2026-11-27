"""Read each supported file type into a Document with page-level text (tables go to tables.py)."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

from forge.ingest import ocr
from forge.ingest.tables import extract_embedded_tables, register_table
from forge.schemas.corpus import Document, Page, TableInfo
from forge.util import slugify

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
TEXT_EXT = {".pdf", ".docx", ".md", ".markdown", ".txt", ".html", ".htm"} | IMAGE_EXT
TABLE_EXT = {".csv", ".xlsx", ".xls"}
SUPPORTED = TEXT_EXT | TABLE_EXT
EXTRACTED_DIR = ".extracted"  # tables found inside documents are written here as CSV (hidden: not re-ingested)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def load_pdf(path: Path) -> tuple[list[Page], str | None, list[str]]:
    import fitz  # pymupdf

    warnings = []
    pages = []
    with fitz.open(str(path)) as pdf:
        title = (pdf.metadata or {}).get("title") or None
        for i, page in enumerate(pdf, start=1):
            text = page.get_text("text") or ""
            if len(text.strip()) < 20:
                ocr_text = ""
                if ocr.budget_left():
                    ocr_text = ocr.ocr_pdf_page(page)
                if len(ocr_text.strip()) >= 10:
                    text = ocr_text
                    warnings.append(f"{path.name} page {i} is a scanned image: text was read with OCR (check quotes)")
                else:
                    why = "OCR unavailable" if not ocr.available() else (
                        "OCR page limit reached" if not ocr.budget_left() else "OCR found no text")
                    warnings.append(f"{path.name} page {i} has almost no text (scanned image?; {why})")
            pages.append(Page(number=i, text=text))
    return pages, title, warnings


def load_image(path: Path) -> tuple[list[Page], str | None, list[str]]:
    """Photos or scans of documents (PNG/JPG/TIFF...): read with OCR."""
    if not ocr.available():
        raise ValueError("image file but OCR is unavailable (pip install rapidocr_onnxruntime)")
    text = ocr.ocr_image_file(path)
    return [Page(number=1, text=text)], path.stem, [f"{path.name} is an image: text was read with OCR (check quotes)"]


def load_docx(path: Path) -> tuple[list[Page], str | None, list[str]]:
    import docx

    d = docx.Document(str(path))
    lines = []
    for p in d.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        if style.startswith("heading"):
            level = re.findall(r"\d", style)
            lines.append("#" * int(level[0] if level else 1) + " " + txt)
        else:
            lines.append(txt)
    for table in d.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    title = d.core_properties.title or None
    return _paginate("\n\n".join(lines)), title, []


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0
        self._heading: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("h1", "h2", "h3"):
            self._heading = "#" * int(tag[1]) + " "
            self.parts.append("\n\n")
        if tag in ("p", "br", "li", "tr", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        if tag in ("h1", "h2", "h3"):
            self._heading = None
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._heading:
            self.parts.append(self._heading)
            self._heading = ""
        self.parts.append(data)


def load_html(path: Path) -> tuple[list[Page], str | None, list[str]]:
    parser = _HTMLText()
    parser.feed(_read_text_file(path))
    return _paginate("".join(parser.parts)), None, []


def load_text(path: Path) -> tuple[list[Page], str | None, list[str]]:
    return _paginate(_read_text_file(path)), None, []


def _paginate(text: str, page_chars: int = 3500) -> list[Page]:
    """Split on form feeds, else into ~page_chars logical pages at paragraph boundaries."""
    if "\f" in text:
        return [Page(number=i, text=t) for i, t in enumerate(text.split("\f"), start=1) if t.strip()]
    pages, buf, n = [], [], 1
    size = 0
    for para in re.split(r"(\n\s*\n)", text):
        buf.append(para)
        size += len(para)
        if size >= page_chars:
            pages.append(Page(number=n, text="".join(buf)))
            buf, size, n = [], 0, n + 1
    if "".join(buf).strip():
        pages.append(Page(number=n, text="".join(buf)))
    return pages or [Page(number=1, text=text)]


LOADERS = {".pdf": load_pdf, ".docx": load_docx, ".md": load_text, ".markdown": load_text, ".txt": load_text,
           ".html": load_html, ".htm": load_html, **{e: load_image for e in IMAGE_EXT}}

_TYPE = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".markdown": "md", ".txt": "txt", ".html": "html",
         ".htm": "html", **{e: "image" for e in IMAGE_EXT}}


def _is_placeholder(path: Path) -> bool:
    """Skip the blueprint README files that sit in demo docs folders until real documents are generated."""
    return path.name.lower() == "readme.md" and "delete this readme" in _read_text_file(path).lower()


def load_folder(docs_dir: Path) -> tuple[list[Document], list[TableInfo], list[str]]:
    """Walk docs_dir recursively. Unsupported/empty files are skipped with a reason."""
    documents: list[Document] = []
    tables: list[TableInfo] = []
    warnings: list[str] = []
    used_ids: set[str] = set()
    extracted_dir = docs_dir / EXTRACTED_DIR
    if extracted_dir.exists():  # regenerate: the documents may have changed since the last ingest
        for old in extracted_dir.glob("*.csv"):
            old.unlink(missing_ok=True)
    for path in sorted(p for p in docs_dir.rglob("*") if p.is_file()):
        rel_parts = path.relative_to(docs_dir).parts
        if any(part.startswith(".") for part in rel_parts) or _is_placeholder(path):
            continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED:
            warnings.append(f"skipped {path.name}: unsupported file type")
            continue
        if path.stat().st_size == 0:
            warnings.append(f"skipped {path.name}: empty file")
            continue
        try:
            if ext in TABLE_EXT:
                tables.extend(register_table(path))
                continue
            pages, title, w = LOADERS[ext](path)
            warnings.extend(w)
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the run
            warnings.append(f"skipped {path.name}: could not read ({exc.__class__.__name__}: {exc})")
            continue
        if not any(p.text.strip() for p in pages):
            warnings.append(f"skipped {path.name}: no extractable text")
            continue
        doc_id = slugify(path.stem)
        base, k = doc_id, 2
        while doc_id in used_ids:
            doc_id, k = f"{base}_{k}", k + 1
        used_ids.add(doc_id)
        documents.append(Document(doc_id=doc_id, path=str(path), type=_TYPE[ext], title=title or path.stem,
                                  sha256=_sha(path), pages=pages))
        # tables inside the document become queryable tables too (the text stays in the chunks as well)
        try:
            for csv_path in extract_embedded_tables(path, ext, doc_id, pages, extracted_dir):
                tables.extend(register_table(csv_path))
                warnings.append(f"{path.name}: found a table ({csv_path.stem}) and made it queryable")
        except Exception as exc:  # noqa: BLE001 - table extraction is a bonus, never a failure
            warnings.append(f"{path.name}: table extraction failed ({exc.__class__.__name__}: {exc})")
    return documents, tables, warnings
