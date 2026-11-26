"""Read-only queries over the registered CSV/XLSX tables. Whitelisted ops only, no query strings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from forge.ingest.tables import read_table
from forge.runtime.tools.base import Tool


class Filter(BaseModel):
    column: str
    op: Literal["eq", "ne", "lt", "lte", "gt", "gte", "contains", "in"] = "eq"
    value: Any


class Aggregate(BaseModel):
    op: Literal["count", "sum", "mean", "min", "max"]
    column: str | None = None


class CsvArgs(BaseModel):
    table: str = Field(description="Table name")
    filters: list[Filter] = Field(default_factory=list)
    select: list[str] | None = None
    sort_by: str | None = None
    descending: bool = False
    limit: int = Field(default=10, ge=1, le=50)
    aggregate: Aggregate | None = None


def _mask(df: pd.DataFrame, f: Filter) -> pd.Series:
    col = df[f.column]
    v = f.value
    numeric = pd.api.types.is_numeric_dtype(col)
    if f.op == "contains":
        return col.astype(str).str.contains(str(v), case=False, na=False, regex=False)
    if f.op == "in":
        vals = v if isinstance(v, list) else [v]
        if numeric:
            return col.isin([float(x) for x in vals])
        return col.astype(str).str.lower().isin([str(x).lower() for x in vals])
    if numeric:
        v = float(v)
    else:
        col, v = col.astype(str).str.lower(), str(v).lower()
    return {"eq": col == v, "ne": col != v, "lt": col < v, "lte": col <= v, "gt": col > v, "gte": col >= v}[f.op]


def query_table(df: pd.DataFrame, args: CsvArgs) -> dict[str, Any]:
    cols = list(df.columns)
    for name in [f.column for f in args.filters] + (args.select or []) + [args.sort_by] + \
            [args.aggregate.column if args.aggregate else None]:
        if name and name not in cols:
            raise ValueError(f"unknown column '{name}'. Valid columns: {cols}")
    out = df
    for f in args.filters:
        out = out[_mask(out, f)]
    if args.aggregate:
        a = args.aggregate
        if a.op == "count":
            value = int(len(out))
        else:
            series = pd.to_numeric(out[a.column], errors="coerce")
            value = getattr(series, a.op)()
            value = None if pd.isna(value) else round(float(value), 4)
        return {"aggregate": a.op, "column": a.column, "value": value, "rows_matched": int(len(out))}
    if args.sort_by:
        out = out.sort_values(args.sort_by, ascending=not args.descending)
    if args.select:
        out = out[args.select]
    rows = out.head(args.limit)
    return {"rows": rows.where(pd.notna(rows), None).to_dict(orient="records"), "row_count": int(len(out)),
            "truncated": len(out) > args.limit}


class CsvLookupTool(Tool):
    name = "csv_lookup"
    description = ("Query a data table: filter rows (eq, ne, lt, lte, gt, gte, contains, in), select columns, "
                   "sort, limit, or aggregate (count, sum, mean, min, max). Use it for any question about "
                   "values stored in the tables.")
    Args = CsvArgs

    def __init__(self, config=None, base_dir=None):
        super().__init__(config, base_dir)
        self._frames: dict[str, pd.DataFrame] = {}
        tables = self.config.get("tables", [])
        self.paths = {t["name"]: Path(t["path"]) for t in tables}

    def _frame(self, name: str) -> pd.DataFrame:
        if name not in self.paths:
            raise ValueError(f"unknown table '{name}'. Available tables: {sorted(self.paths)}")
        if name not in self._frames:
            p = self.paths[name]
            if not p.is_absolute():
                p = self.base_dir / p
            self._frames[name] = read_table(p)
        return self._frames[name]

    def _run(self, args: CsvArgs):
        return {"table": args.table, **query_table(self._frame(args.table), args)}

    def describe(self) -> str:
        lines = [super().describe()]
        for name in self.paths:
            try:
                lines.append(f"  table '{name}' columns: {list(self._frame(name).columns)}")
            except Exception:  # noqa: BLE001
                continue
        return "\n".join(lines)
