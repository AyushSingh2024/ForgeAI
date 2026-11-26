"""Loaders, chunker and tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.errors import BadInput
from forge.ingest.chunker import chunk_document
from forge.ingest.loaders import load_folder
from forge.ingest.tables import table_card


def test_load_folder_separates_tables(tiny_corpus):
    docs, tables, warnings = load_folder(tiny_corpus)
    assert {d.doc_id for d in docs} == {"membership_rules", "refund_policy", "opening_hours"}
    assert [t.name for t in tables] == ["classes"]
    assert tables[0].row_count == 10
    assert "with the csv_lookup tool" in table_card(tables[0])


def test_chunk_provenance_and_size(tiny_corpus):
    docs, _, _ = load_folder(tiny_corpus)
    doc = next(d for d in docs if d.doc_id == "membership_rules")
    chunks = chunk_document(doc, chunk_size=60, overlap=10)
    assert len(chunks) >= 3
    pages = {p.number: p.text for p in doc.pages}
    for c in chunks:
        assert c.text == pages[c.page][c.char_start:c.char_end]
        assert c.token_count <= 60 * 2.5  # a chunk may run one sentence + the overlap past the target size
    assert any("Guests" in " ".join(c.section_path) for c in chunks)


def test_skips_unsupported_and_empty(tmp_path: Path):
    (tmp_path / "a.exe").write_bytes(b"x")
    (tmp_path / "empty.txt").write_text("")
    docs, tables, warnings = load_folder(tmp_path)
    assert not docs and not tables
    assert len(warnings) == 2


def test_empty_folder_raises(tmp_path, cfg, make_fake_hub):
    from forge.context import RunContext
    from forge.ingest import run_ingest

    (tmp_path / "input" / "docs").mkdir(parents=True)
    ctx = RunContext(run_dir=tmp_path, cfg=cfg, hub=make_fake_hub())
    with pytest.raises(BadInput):
        run_ingest(ctx)
