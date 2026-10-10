import re
from collections import Counter
from dataclasses import dataclass

import pymupdf


@dataclass
class Line:
    page: int
    text: str
    bbox: list[float]
    size: float
    bold: bool


@dataclass
class PdfDoc:
    path: str
    pages: int
    lines: list[Line]
    body_size: float
    page_size: tuple[float, float]


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def _page_rows(page: pymupdf.Page, page_no: int) -> list[Line]:
    """Merge PyMuPDF lines that sit on the same visual row (e.g. '5.1' and its title in separate blocks)."""
    raw = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if spans:
                raw.append((line["bbox"], spans))
    raw.sort(key=lambda r: (round(r[0][1]), r[0][0]))

    rows: list[list] = []
    for bbox, spans in raw:
        mid = (bbox[1] + bbox[3]) / 2
        if rows and abs(rows[-1][0] - mid) < 3:
            rows[-1][1].append((bbox, spans))
        else:
            rows.append([mid, [(bbox, spans)]])

    lines = []
    for _, parts in rows:
        parts.sort(key=lambda p: p[0][0])
        spans = [s for _, ss in parts for s in ss]
        text = re.sub(r"\s+", " ", " ".join(s["text"] for s in spans)).strip()
        main = max(spans, key=lambda s: len(s["text"].strip()))
        bbox = [min(p[0][0] for p in parts), min(p[0][1] for p in parts),
                max(p[0][2] for p in parts), max(p[0][3] for p in parts)]
        lines.append(Line(page_no, text, [round(v, 1) for v in bbox], round(main["size"], 1),
                          all(_is_bold(s) for s in spans if s["text"].strip())))
    return lines


def _strip_running_text(lines: list[Line], n_pages: int, page_height: float) -> list[Line]:
    """Drop headers and footers: short lines in the top/bottom bands that repeat on many pages."""
    def key(line: Line) -> str:
        return re.sub(r"\d+", "#", line.text.lower())

    def in_band(line: Line) -> bool:
        return line.bbox[1] < 72 or line.bbox[3] > page_height - 72

    counts = Counter(key(ln) for ln in lines if in_band(ln))
    repeated = {k for k, c in counts.items() if c >= max(3, n_pages * 0.3)}
    return [ln for ln in lines if not (in_band(ln) and key(ln) in repeated)]


def read_pdf(path: str) -> PdfDoc:
    doc = pymupdf.open(path)
    lines = [ln for i, page in enumerate(doc, 1) for ln in _page_rows(page, i)]
    width, height = doc[0].rect.width, doc[0].rect.height
    lines = _strip_running_text(lines, len(doc), height)
    sizes = Counter()
    for ln in lines:
        sizes[ln.size] += len(ln.text)
    body = sizes.most_common(1)[0][0] if sizes else 11.0
    return PdfDoc(path, len(doc), lines, body, (width, height))
