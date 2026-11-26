"""Register CSV/XLSX files as queryable tables instead of prose, plus a text 'table card' for retrieval."""

from __future__ import annotations

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


def read_table(path: Path, sheet: str | int | None = None) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        try:
            df = pd.read_csv(path)
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="cp1252")
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
        return [_info(slugify(path.stem), path, read_table(path))]
    out = []
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        df = normalise_columns(pd.read_excel(path, sheet_name=sheet))
        if df.empty:
            continue
        name = slugify(path.stem if len(xls.sheet_names) == 1 else f"{path.stem}_{sheet}")
        out.append(_info(name, path, df))
    return out


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
