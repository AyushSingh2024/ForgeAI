"""Unseen-input robustness: messy CSVs, text without punctuation, and the guard's second opinion."""

from __future__ import annotations

import pytest

from forge.guard.guard import mentioned_in_corpus
from forge.ingest.chunker import chunk_document
from forge.ingest.tables import read_table, register_table
from forge.schemas.corpus import Document, Page


@pytest.mark.parametrize("data", [
    "id;name;price\n1;Bolt;2\n2;Nut;3\n".encode(),
    "Quarterly report,,\n,,\nid,name,price\n1,Bolt,2\n2,Nut,3\n".encode(),
    "id,name,price\n1,Bolt,2\n2,Nut,3\n".encode("utf-16"),
    "id,name,price\n1,Bolt,2\n9,x,y,z,extra\n2,Nut,3\n".encode(),
])
def test_messy_csv(tmp_path, data):
    p = tmp_path / "t.csv"
    p.write_bytes(data)
    df = read_table(p)
    assert list(df.columns) == ["id", "name", "price"] and len(df) == 2


def test_header_only_table_is_rejected(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("a,b\n")
    with pytest.raises(ValueError):
        register_table(p)


def test_text_without_punctuation_is_split():
    doc = Document(doc_id="d", path="d.txt", type="txt", pages=[Page(number=1, text="word " * 5000)])
    chunks = chunk_document(doc, 200, 20)
    assert len(chunks) > 10 and max(c.token_count for c in chunks) <= 400


def test_guard_second_opinion():
    vocab = {"tuition", "fees", "undergraduate", "programmes", "hostel", "allocation"}
    assert mentioned_in_corpus("Fees: what are the tuition fees for undergraduate programmes?", vocab)
    assert not mentioned_in_corpus("Is parking free for visitors?", vocab)
    assert not mentioned_in_corpus("Current tuition fees today", vocab)
