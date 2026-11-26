"""Tiny helper to render simple markdown-like text to PDF with page numbers (dev dependency: fpdf2)."""

from __future__ import annotations

from pathlib import Path

_REPL = {"–": "-", "—": "-", "’": "'", "“": '"', "”": '"', "°": " deg "}


def _latin(text: str) -> str:
    for a, b in _REPL.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def write_pdf(path: Path, title: str, body: str, org: str) -> None:
    from fpdf import FPDF

    class Doc(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", size=8)
            self.cell(0, 8, _latin(f"{org} - {title} - page {self.page_no()}"), align="C")

    pdf = Doc(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    def para(height: float, text: str) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, height, _latin(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 16)
    para(9, title)
    pdf.ln(2)
    for raw in body.strip().splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            para(7, line[3:])
        elif line.startswith("| "):
            pdf.set_font("Courier", size=8)
            para(4.5, line)
        elif not line:
            pdf.ln(2)
        else:
            pdf.set_font("Helvetica", size=10)
            para(5.5, line)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
