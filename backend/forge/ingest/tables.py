"""Register CSV/XLSX files as queryable tables instead of prose, plus a text 'table card' for retrieval."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

from forge.schemas.corpus import Chunk, ColumnInfo, TableInfo
from forge.util import count_tokens, slugify


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") or f"col_{i}"
                  for i, c in enumerate(df.columns)]
    return df


def _read_csv(path: Path) -> pd.DataFrame:
    """Tolerant CSV reading: UTF-8/UTF-16/cp1252, comma/semicolon/tab/pipe, title rows above the header,
    and ragged rows (rows with extra fields are skipped rather than failing the whole file)."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        if b"\x00" in raw:
            raise ValueError("file looks binary, not CSV")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip(" ,;\t|")]
    if not lines:
        raise ValueError("no rows")
    sample = lines[:30]

    def cells(line: str, d: str) -> list[str]:
        return next(csv.reader([line], delimiter=d))

    delim = max(",;\t|", key=lambda d: sorted(len(cells(ln, d)) for ln in sample)[len(sample) // 2])
    widths = [sum(1 for c in cells(ln, delim) if c.strip()) for ln in sample]
    typical = sorted(widths)[len(widths) // 2]
    start = 0
    while start < len(sample) - 1 and typical > 1 and widths[start] <= 1:  # title rows above the real header
        start += 1
    return pd.read_csv(io.StringIO("\n".join(lines[start:])), sep=delim, on_bad_lines="skip", skipinitialspace=True)


def read_table(path: Path, sheet: str | int | None = None) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = _read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=sheet or 0)
    return normalise_columns(df)


def _info(name: str, path: Path, df: pd.DataFrame) -> TableInfo:
    cols = []
    for c in df.columns:
        dtype = "number" if pd.api.types.is_numeric_dtype(df[c]) else "text"
        samples = [v for v in df[c].dropna().unique()[:3].tolist()]
        cols.append(ColumnInfo(name=c, dtype=dtype, sample_values=samples))
    sample_rows = df.head(5).where(pd.notna(df.head(5)), None).to_dict(orient="records")
    return TableInfo(name=name, path=str(path), columns=cols, row_count=int(len(df)), sample_rows=sample_rows)


def register_table(path: Path) -> list[TableInfo]:
    if path.suffix.lower() == ".csv":
        df = read_table(path)
        if df.empty:
            raise ValueError("table has a header but no data rows")
        return [_info(slugify(path.stem), path, df)]
    out = []
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        df = normalise_columns(pd.read_excel(path, sheet_name=sheet))
        if df.empty:
            continue
        name = slugify(path.stem if len(xls.sheet_names) == 1 else f"{path.stem}_{sheet}")
        out.append(_info(name, path, df))
    return out


_PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_SEP_ROW = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _clean_frame(df: pd.DataFrame) -> pd.DataFrame | None:
    """Keep a table only if it looks like a real table: >= 2 columns, >= 1 data row, a mostly filled header."""
    if df is None or df.empty:
        return None
    df = df.copy()
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, [bool(str(c).strip()) or df[c].notna().any() for c in df.columns]]
    df = df.dropna(axis=0, how="all")
    if df.shape[1] < 2 or df.shape[0] < 1:
        return None
    named = sum(1 for c in df.columns if str(c).strip() and not str(c).lower().startswith(("col", "unnamed")))
    if named < max(2, df.shape[1] // 2):
        return None
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].map(lambda v: v.replace("\n", " ").strip() if isinstance(v, str) else v)
            num = pd.to_numeric(df[c].map(lambda v: re.sub(r"[,\s]", "", v) if isinstance(v, str) else v),
                                errors="coerce")
            if num.notna().sum() == df[c].notna().sum() and num.notna().any():
                df[c] = num
    return df


def pipe_tables(text: str) -> list[pd.DataFrame]:
    """Markdown / pipe-delimited tables inside text (| a | b |), including PDF text that kept the pipes."""
    out, block = [], []
    for line in text.splitlines() + [""]:
        if _PIPE_ROW.match(line):
            block.append(line)
            continue
        if len(block) >= 3:
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in block if not _SEP_ROW.match(ln)]
            header, body = rows[0], [r for r in rows[1:] if len(r) == len(rows[0])]
            if body:
                df = _clean_frame(pd.DataFrame(body, columns=header))
                if df is not None:
                    out.append(df)
        block = []
    return out


def extract_embedded_tables(path: Path, ext: str, doc_id: str, pages, out_dir: Path) -> list[Path]:
    """Find tables inside a PDF / DOCX / text document and save each as CSV so csv_lookup can query it."""
    found: list[tuple[str, pd.DataFrame]] = []
    if ext == ".pdf":
        import fitz

        with fitz.open(str(path)) as pdf:
            for pno, page in enumerate(pdf, start=1):
                try:
                    tabs = page.find_tables()  # ruled tables (drawn lines)
                except Exception:  # noqa: BLE001
                    continue
                for k, tab in enumerate(tabs.tables, start=1):
                    df = _clean_frame(tab.to_pandas())
                    if df is not None:
                        found.append((f"p{pno}_t{k}", df))
    elif ext == ".docx":
        import docx

        for k, t in enumerate(docx.Document(str(path)).tables, start=1):
            rows = [[c.text.strip() for c in r.cells] for r in t.rows]
            if len(rows) >= 2:
                df = _clean_frame(pd.DataFrame(rows[1:], columns=rows[0]))
                if df is not None:
                    found.append((f"t{k}", df))
    if not found:  # pipe tables in the extracted text (markdown, txt, and PDFs that kept the pipes)
        for page in pages:
            for k, df in enumerate(pipe_tables(page.text), start=1):
                found.append((f"p{page.number}_t{k}", df))
    paths = []
    if found:
        out_dir.mkdir(parents=True, exist_ok=True)
    for label, df in found[:20]:
        csv_path = out_dir / f"{doc_id}_{label}.csv"
        df.to_csv(csv_path, index=False)
        paths.append(csv_path)
    return paths


def table_card(table: TableInfo) -> str:
    cols = ", ".join(f"{c.name} ({c.dtype}, e.g. {', '.join(map(str, c.sample_values[:2]))})" for c in table.columns)
    example = table.sample_rows[0] if table.sample_rows else {}
    return (f"Table '{table.name}' has {table.row_count} rows. This passage only DESCRIBES the table: to answer any "
            f"question about its rows or values, query it with the csv_lookup tool. Columns: {cols}. "
            f"Example row (format only): {example}")


def table_card_chunk(table: TableInfo) -> Chunk:
    text = table_card(table)
    return Chunk(chunk_id=f"table:{table.name}", doc_id=f"table:{table.name}", page=1,
                 section_path=[f"Table {table.name}"], char_start=0, char_end=len(text), text=text,
                 token_count=count_tokens(text))
