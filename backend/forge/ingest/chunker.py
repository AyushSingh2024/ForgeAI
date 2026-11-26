"""Split Documents into Chunks while keeping provenance.

Invariant (tested): chunk.text == page.text[chunk.char_start:chunk.char_end]. Chunks never cross a page,
so every citation has a page number. Headings are tracked as a section_path and prepended only to the
text that gets embedded (Chunk.embed_text), not to the stored text.
"""

from __future__ import annotations

import re

from forge.schemas.corpus import Chunk, Document
from forge.util import count_tokens

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUM_HEADING = re.compile(r"^((?:\d+\.)*\d+)\.?\s+([A-Z][^\n]{1,80})$")
_PARA = re.compile(r"(?:[^\n]|\n(?![ \t\r]*\n))+")  # \r: tolerate Windows line endings
_SENT = re.compile(r"[^.!?\n]+(?:[.!?]+|\n|$)")


def _heading(line: str) -> tuple[int, str] | None:
    s = line.strip()
    if not s or len(s) > 100:
        return None
    m = _MD_HEADING.match(s)
    if m:
        return len(m.group(1)), m.group(2).strip()
    m = _NUM_HEADING.match(s)
    if m and not s.endswith((".", ",", ";")) and len(s.split()) <= 12:
        return m.group(1).count(".") + 1, s
    letters = [c for c in s if c.isalpha()]
    if len(letters) >= 4 and all(c.isupper() for c in letters) and len(s.split()) <= 10:
        return 1, s.title()
    return None


def _spans(text: str):
    """Paragraph spans, additionally split before any heading line inside a paragraph.
    PDF text often has no blank lines at all, so headings would otherwise be buried mid-paragraph."""
    for m in _PARA.finditer(text):
        start, end = m.start(), m.end()
        pos = start
        cut = start
        while pos < end:
            nl = text.find("\n", pos, end)
            line_end = end if nl == -1 else nl
            if pos > cut and _heading(text[pos:line_end]):
                yield cut, pos
                cut = pos
            if nl == -1:
                break
            pos = nl + 1
        yield cut, end


def _push(stack: list[tuple[int, str]], level: int, title: str) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


def chunk_document(doc: Document, chunk_size: int = 600, overlap: int = 90) -> list[Chunk]:
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    max_chars = chunk_size * 4
    overlap_chars = overlap * 4
    n = 0

    for page in doc.pages:
        text = page.text
        # 1) blocks = paragraphs with offsets, headings update the section stack
        blocks: list[tuple[int, int, list[str]]] = []
        for start, end in _spans(text):
            raw = text[start:end]
            start += len(raw) - len(raw.lstrip())  # a match can begin with the blank line's own newline
            if start >= end:
                continue
            first_nl = text.find("\n", start, end)
            first_line = text[start:first_nl if first_nl != -1 else end]
            h = _heading(first_line)
            if h:
                _push(stack, *h)
                if first_nl == -1:
                    continue
                start = first_nl + 1
            seg = text[start:end]
            if not seg.strip():
                continue
            # shift start past leading whitespace
            start += len(seg) - len(seg.lstrip())
            path = [t for _, t in stack]
            if end - start > max_chars:
                # 2) long paragraph -> sentence pieces
                s0 = start
                for sm in _SENT.finditer(text, start, end):
                    if sm.end() - s0 >= max_chars:
                        blocks.append((s0, sm.end(), path))
                        s0 = sm.end()
                if end > s0 and text[s0:end].strip():
                    blocks.append((s0, end, path))
            else:
                blocks.append((start, end, path))

        # 3) greedy pack blocks into chunks (same page, same top section preferred)
        cur_start: int | None = None
        cur_end = 0
        cur_path: list[str] = []
        prev_end: int | None = None

        def flush() -> None:
            nonlocal cur_start, n, prev_end
            if cur_start is None:
                return
            start = cur_start
            if prev_end is not None and overlap_chars > 0:
                start = max(0, min(cur_start, prev_end - overlap_chars))
                # snap overlap start to a word boundary
                sp = text.find(" ", start, cur_start)
                start = sp + 1 if sp != -1 else start
            body = text[start:cur_end]
            n_local = len(chunks)
            chunks.append(Chunk(chunk_id=f"{doc.doc_id}#p{page.number}#{n_local}", doc_id=doc.doc_id,
                                page=page.number, section_path=list(cur_path), char_start=start, char_end=cur_end,
                                text=body, token_count=count_tokens(body)))
            n += 1
            prev_end = cur_end
            cur_start = None

        for b_start, b_end, path in blocks:
            new_section = cur_path != path  # a new (sub)section starts a new chunk: cleaner citations
            if cur_start is not None and (b_end - cur_start > max_chars or new_section):
                flush()
            if cur_start is None:
                cur_start, cur_path = b_start, path
            cur_end = b_end
        flush()

    return chunks


def chunk_documents(docs: list[Document], chunk_size: int, overlap: int) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        out.extend(chunk_document(d, chunk_size, overlap))
    return out
