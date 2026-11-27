"""Documents, chunks, tables and the corpus profile."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DocType = Literal["pdf", "docx", "md", "txt", "html", "csv", "xlsx", "image"]


class Page(BaseModel):
    number: int
    text: str


class Document(BaseModel):
    doc_id: str
    path: str
    type: DocType
    title: str | None = None
    sha256: str = ""
    pages: list[Page] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    page: int
    section_path: list[str] = Field(default_factory=list)
    char_start: int = 0
    char_end: int = 0
    text: str
    token_count: int = 0

    def embed_text(self) -> str:
        prefix = " > ".join(self.section_path)
        return f"{prefix}\n{self.text}" if prefix else self.text


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    sample_values: list[Any] = Field(default_factory=list)


class TableInfo(BaseModel):
    name: str
    path: str
    columns: list[ColumnInfo] = Field(default_factory=list)
    row_count: int = 0
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class DocProfile(BaseModel):
    doc_id: str
    title: str
    pages: int
    summary: str = ""
    top_keywords: list[str] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)


class CorpusProfile(BaseModel):
    documents: list[DocProfile] = Field(default_factory=list)
    tables: list[TableInfo] = Field(default_factory=list)
    language: str = "en"
    total_tokens: int = 0
    n_chunks: int = 0
    numeric_density: float = 0.0
    median_section_tokens: int = 0
    warnings: list[str] = Field(default_factory=list)
