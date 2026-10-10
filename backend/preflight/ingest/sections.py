import re

from preflight.graph.models import Section
from preflight.ingest.pdf import Line, PdfDoc

NUMBERED = re.compile(r"^((?:\d{1,2}\.)*\d{1,2})\.?\s+([A-Z][^\n]{1,150})$")
APPENDIX = re.compile(r"^(appendix\s+[A-Z0-9]+)[\s:.\-–]+(.{2,150})$", re.I)
DOT_LEADER = re.compile(r"(\.\s*){4,}\d+\s*$|\s\d{1,3}$")


def _toc_pages(lines: list[Line]) -> set[int]:
    per_page: dict[int, int] = {}
    for ln in lines:
        if DOT_LEADER.search(ln.text):
            per_page[ln.page] = per_page.get(ln.page, 0) + 1
    return {p for p, n in per_page.items() if n >= 5}


def _heading(ln: Line, body_size: float) -> tuple[str | None, str, int] | None:
    """Return (number, title, level) if this line looks like a section heading."""
    if DOT_LEADER.search(ln.text) or len(ln.text) > 160:
        return None
    styled = ln.bold or ln.size > body_size + 0.5
    if not styled:
        return None
    if m := NUMBERED.match(ln.text):
        number, title = m.groups()
        if int(number.split(".")[0]) > 30 or title.rstrip().endswith((",", ";")):
            return None
        return number, title.strip(), number.count(".") + 1
    if m := APPENDIX.match(ln.text):
        return m.group(1).title(), m.group(2).strip(), 1
    if ln.text.isupper() and 3 <= len(ln.text) <= 80 and ln.size >= body_size and re.search(r"[A-Z]{3}", ln.text):
        return None, ln.text.title(), 1
    return None


def _is_next(prev: str | None, number: str) -> bool:
    """Reject numbered lines that break the outline (e.g. list items '3. Patients must...')."""
    if prev is None:
        return True
    p, n = [int(x) for x in prev.split(".")], [int(x) for x in number.split(".")]
    for depth in range(len(n)):
        if n[:depth] != p[:depth]:
            return False
        if depth == len(n) - 1:
            expected = p[depth] + 1 if depth < len(p) else 1
            return n[depth] in (expected, expected + 1) or (depth >= len(p) and n[depth] <= 2)
    return False


def _continuation(head: Line, prev: Line, ln: Line) -> bool:
    """A wrapped heading line: same page and style, directly below, not a new numbered heading."""
    return (ln.page == head.page and ln.bold == head.bold and abs(ln.size - head.size) <= 0.5
            and -3 <= ln.bbox[1] - prev.bbox[3] < head.size * 0.8
            and not NUMBERED.match(ln.text) and not DOT_LEADER.search(ln.text)
            and not re.match(r"(table|figure)\s+\d", ln.text, re.I)
            and not prev.text.rstrip().endswith((".", ":")))


def split_sections(doc: PdfDoc) -> list[tuple[Section, list[Line]]]:
    """Sections with the body lines that belong to each one (TOC pages excluded)."""
    skip = _toc_pages(doc.lines)
    heads: list[tuple[int, int, str | None, str, int]] = []
    last_number = None
    i = 0
    while i < len(doc.lines):
        ln = doc.lines[i]
        if ln.page in skip or not (h := _heading(ln, doc.body_size)):
            i += 1
            continue
        number, title, level = h
        if number and not number.lower().startswith("appendix"):
            if not _is_next(last_number, number):
                i += 1
                continue
            last_number = number
        j = i + 1
        while j < len(doc.lines) and j - i <= 4 and _continuation(ln, doc.lines[j - 1], doc.lines[j]):
            extra = doc.lines[j].text
            title += " " + (extra.title() if number is None else extra)
            j += 1
        heads.append((i, j, number, title, level))
        i = j

    # Fold runs of empty unnumbered headings (title pages, label blocks) into the next heading.
    folded = []
    for h in heads:
        prev = folded[-1] if folded else None
        if prev and prev[2] is None and h[2] is None and prev[1] == h[0] and len(prev[3]) < 200:
            folded[-1] = (prev[0], h[1], None, f"{prev[3]} {h[3]}", 1)
        else:
            folded.append(h)
    heads = folded

    sections = []
    for k, (i, j, number, title, level) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(doc.lines)
        body = [ln for ln in doc.lines[j:end] if ln.page not in skip]
        sections.append((Section(
            id=f"sec_{k + 1}",
            m11_id=None,
            title=f"{number} {title}" if number else title,
            level=level,
            page_start=doc.lines[i].page,
            page_end=body[-1].page if body else doc.lines[i].page,
            text="\n".join(ln.text for ln in body),
        ), body))
    return sections


def find_sections(doc: PdfDoc) -> list[Section]:
    return [s for s, _ in split_sections(doc)]
