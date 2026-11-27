"""Scanned pages are read with OCR; tables inside PDFs, DOCX and markdown become queryable tables."""

from __future__ import annotations

import pytest

from forge.ingest import ocr
from forge.ingest.loaders import EXTRACTED_DIR, load_folder
from forge.ingest.tables import pipe_tables
from forge.runtime.tools.csv_lookup import CsvLookupTool


def _scanned_pdf(path, text):
    import fitz

    src = fitz.open()
    page = src.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    pix = page.get_pixmap(dpi=150)
    out = fitz.open()
    p2 = out.new_page()
    p2.insert_image(p2.rect, pixmap=pix)
    out.save(str(path))


def _ruled_pdf(path):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "Tuition fees 2026, per academic year.", new_x="LMARGIN", new_y="NEXT")
    with pdf.table() as table:
        for row in [("Programme", "Fee per year (EUR)"), ("BSc Computing", "5,400"), ("MSc Data", "7,900")]:
            r = table.row()
            for cell in row:
                r.cell(cell)
    pdf.output(str(path))


def test_pipe_tables_parsed():
    text = "Intro\n| Item | Price |\n|---|---|\n| Tent | 120 |\n| Stove | 55 |\nEnd"
    [df] = pipe_tables(text)
    assert list(df.columns) == ["Item", "Price"] and df["Price"].sum() == 175


def test_prose_with_pipes_is_not_a_table():
    assert pipe_tables("a | b\nc | d\n") == []


def test_ruled_pdf_table_becomes_queryable(tmp_path):
    _ruled_pdf(tmp_path / "fees.pdf")
    docs, tables, warnings = load_folder(tmp_path)
    assert docs and tables and (tmp_path / EXTRACTED_DIR).exists()
    t = tables[0]
    tool = CsvLookupTool(config={"tables": [{"name": t.name, "path": t.path}]})
    res = tool.run({"table": t.name, "aggregate": {"op": "max", "column": "fee_per_year_eur"}})
    assert res.ok and res.data["value"] == 7900
    # re-ingesting must not pick up the extracted CSVs as extra documents/tables
    docs2, tables2, _ = load_folder(tmp_path)
    assert len(tables2) == len(tables) and len(docs2) == len(docs)


def test_docx_table(tmp_path):
    import docx

    d = docx.Document()
    d.add_paragraph("Fees")
    t = d.add_table(rows=3, cols=2)
    for i, (a, b) in enumerate([("Course", "Fee"), ("BSc", "5000"), ("MSc", "8000")]):
        t.cell(i, 0).text, t.cell(i, 1).text = a, b
    d.save(tmp_path / "fees.docx")
    _, tables, _ = load_folder(tmp_path)
    assert [c.name for c in tables[0].columns] == ["course", "fee"] and tables[0].row_count == 2


@pytest.mark.skipif(not ocr.available(), reason="OCR engine not installed")
def test_scanned_pdf_is_read_with_ocr(tmp_path):
    _scanned_pdf(tmp_path / "scan.pdf", "The late fee is 250 EUR")
    docs, _, warnings = load_folder(tmp_path)
    assert docs and "250" in docs[0].pages[0].text
    assert any("OCR" in w for w in warnings)
