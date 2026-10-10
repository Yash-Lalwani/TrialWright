import re
from collections import Counter

import pdfplumber
import pymupdf
from pydantic import BaseModel

from preflight.graph.models import SoA, Span, Visit, Procedure
from preflight.ingest.pdf import PdfDoc, clean_text

MARK_TOKEN = re.compile(r"(?<![\w-])[xX✓√●](?![\w-])")
MARK_CELL = re.compile(r"^[xX✓√●•](?![A-Za-z]{2})")
HEADER_WORDS = re.compile(r"\b(day|days|week|visit|cycle|screening|month)\b", re.I)


def _cell(text: str | None) -> str:
    text = clean_text((text or "").replace("＋", "+").replace("−", "-").replace("–", "-"))
    return re.sub(r"(?<![\w)])-\s+(?=\d)", "-", text)


def _unrotate(text: str) -> str:
    """Rotated header text comes out reversed ('0 ot 82- syaD')."""
    rev = text[::-1]
    return rev if HEADER_WORDS.search(rev) and not HEADER_WORDS.search(text) else text


def _candidate_pages(doc: PdfDoc) -> list[int]:
    counts = Counter()
    for ln in doc.lines:
        counts[ln.page] += len(MARK_TOKEN.findall(ln.text))
    return sorted(p for p, n in counts.items() if n >= 8)


def _cycle_days(doc: PdfDoc) -> int | None:
    text = " ".join(ln.text for ln in doc.lines[:3000]).lower()
    if m := re.search(r"(\d{1,2})[- ]day (?:treatment )?cycles?", text):
        return int(m.group(1))
    if m := re.search(r"(\d)[- ]week (?:treatment )?cycles?", text):
        return int(m.group(1)) * 7
    if m := re.search(r"\bq(\d)w\b", text):
        return int(m.group(1)) * 7
    return None


def _first_number(text: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else None


def _window(text: str, plus_minus_only: bool = False) -> tuple[float | None, float | None]:
    if m := re.search(r"±\s*(\d+)", text):
        return float(m.group(1)), float(m.group(1))
    if plus_minus_only:
        return None, None
    if m := re.search(r"\+\s*(\d+)", text):
        return 0.0, float(m.group(1))
    if m := re.search(r"(?<!\d)-\s*(\d+)\b", text):
        return float(m.group(1)), 0.0
    return None, None


def _day_from_name(name: str, cycle_len: int | None) -> float | None:
    low = name.lower()
    if m := re.search(r"\b(?:cycles?|cc?s?)\s*(\d+)(?:\s*-\s*\d+)?\D{0,16}?(?:day|d)\s*(-?\d+)", low):
        n, d = int(m.group(1)), int(m.group(2))
        return float((n - 1) * cycle_len + d) if cycle_len else None
    if m := re.search(r"\bweek\s*(\d+)", low):
        return float(int(m.group(1)) * 7 + 1)
    if m := re.search(r"\bdays?\s*(-?\d+)", low):
        return float(m.group(1))
    if "baseline" in low:
        return 1.0
    return None


def _strip_footnote(text: str, procedure: bool = False) -> str:
    text = re.sub(r"(\s+[a-z](,\s*[a-z])*)+$", "", text.strip())
    text = re.sub(r"\s+[a-z](?:,\s*[a-z])*(?=\s*\()", "", text)
    text = re.sub(r"(?<=[a-z)])\d{1,2}$", "", text)
    if procedure:
        text = re.sub(r"(?<=[A-Z])\d{1,2}$", "", text) if len(text) > 4 else text
    return text.strip(" ,")


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _parse_table(rows: list[list[str]], cycle_len: int | None) -> dict | None:
    first_mark = next((i for i, r in enumerate(rows) if any(MARK_CELL.match(c) for c in r[1:])), None)
    if first_mark is None or first_mark == 0:
        return None
    n_cols = len(rows[0])
    header, body = rows[:first_mark], rows[first_mark:]
    day_row = next((r for r in header if re.match(r"^(study )?days?$", r[0], re.I)), None)
    win_row = next((r for r in header if re.match(r"^(time )?window", r[0], re.I)), None)
    name_rows = [r for r in header if r is not day_row and r is not win_row]

    visits = []
    for col in range(1, n_cols):
        parts = []
        for k, r in enumerate(name_rows):
            cell = _unrotate(r[col])
            if k == 0 and not cell:
                continue
            if k == 0 and col + 1 < n_cols and not r[col + 1] and len(name_rows) > 1:
                continue  # group label spanning several columns
            if cell:
                parts.append(_strip_footnote(cell))
        name = " ".join(parts)
        if not name:
            continue
        day_text = day_row[col] if day_row and day_row[col] else name
        day = None if re.search(r"\b(after|every|post)\b", day_text, re.I) else (
            _first_number(day_text) if day_row and day_row[col] else _day_from_name(name, cycle_len))
        wm, wp = _window(win_row[col]) if win_row else _window(name, plus_minus_only=True)
        visits.append((col, name, day, wm, wp))

    procedures = []
    for r in body:
        name = _strip_footnote(r[0], procedure=True)
        marks = {col for col in range(1, n_cols) if MARK_CELL.match(r[col])}
        if name and marks:
            procedures.append((name, marks))
    if len(visits) < 2 or not procedures:
        return None
    return {"visits": visits, "procedures": procedures, "signature": tuple(v[1] for v in visits)}


def _reread_header(rows: list[list[str]], table, page: pymupdf.Page) -> None:
    """pdfplumber scrambles rotated header text; PyMuPDF reads it correctly when clipped to the cell."""
    for i, row in enumerate(table.rows):
        if any(MARK_CELL.match(c) for c in rows[i][1:]):
            break
        for j, bbox in enumerate(row.cells):
            if bbox and j < len(rows[i]) and rows[i][j]:
                rows[i][j] = _cell(page.get_text("text", clip=pymupdf.Rect(bbox)))


def extract_soa(path: str, doc: PdfDoc) -> SoA | None:
    pages = _candidate_pages(doc)
    if not pages:
        return None
    cycle_len = _cycle_days(doc)
    parsed = []
    with pdfplumber.open(path) as pdf, pymupdf.open(path) as mu:
        for pn in pages:
            page = pdf.pages[pn - 1]
            for table in page.find_tables():
                rows = [[_cell(c) for c in row] for row in table.extract()]
                _reread_header(rows, table, mu[pn - 1])
                if rows and (t := _parse_table(rows, cycle_len)):
                    t["page"], t["bbox"] = pn, [round(v, 1) for v in table.bbox]
                    t["marks"] = sum(len(m) for _, m in t["procedures"])
                    parsed.append(t)
    if not parsed:
        return None

    groups: dict[tuple, list[dict]] = {}
    for t in parsed:
        groups.setdefault(t["signature"], []).append(t)
    main = max(groups.values(), key=lambda g: sum(t["marks"] for t in g))

    first = main[0]
    visits = [Visit(id=f"v{i + 1}", name=name, study_day=day, window_minus=wm, window_plus=wp)
              for i, (_, name, day, wm, wp) in enumerate(first["visits"])]
    col_to_visit = {col: visits[i].id for i, (col, *_) in enumerate(first["visits"])}

    procedures: dict[str, Procedure] = {}
    cells: dict[str, dict[str, bool]] = {v.id: {} for v in visits}
    for t in main:
        for name, marks in t["procedures"]:
            norm = _normalize(name)
            if norm not in procedures:
                procedures[norm] = Procedure(id=f"p{len(procedures) + 1}", name=name, normalized_name=norm)
            pid = procedures[norm].id
            for col, vid in col_to_visit.items():
                cells[vid][pid] = cells[vid].get(pid, False) or col in marks

    quote = f"Schedule of Activities: {len(visits)} visits, {len(procedures)} procedures"
    return SoA(visits=visits, procedures=list(procedures.values()), cells=cells,
               span=Span(page=first["page"], bbox=first["bbox"], quote=quote))


class _VisitDay(BaseModel):
    visit_id: str
    study_day: float | None


class _VisitDays(BaseModel):
    visits: list[_VisitDay]


async def fill_days_with_llm(soa: SoA, context: str) -> SoA:
    """Ask the LLM for study days the table did not state (e.g. cycle visits with unknown cycle length)."""
    missing = [v for v in soa.visits if v.study_day is None]
    if not missing:
        return soa
    from preflight.llm.client import complete_json

    names = "\n".join(f"{v.id}: {v.name}" for v in soa.visits)
    out = await complete_json(
        "extract_soa",
        "Give the study day for each Schedule of Activities visit (Day 1 = first dose). "
        "Use null for unscheduled or event-driven visits.",
        f"Protocol context:\n{context[:3000]}\n\nVisits:\n{names}",
        _VisitDays,
    )
    days = {v.visit_id: v.study_day for v in out.visits}
    visits = [v.model_copy(update={"study_day": days.get(v.id)}) if v.study_day is None else v for v in soa.visits]
    return soa.model_copy(update={"visits": visits})
