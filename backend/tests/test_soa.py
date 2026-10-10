import pymupdf

from preflight.ingest.pdf import read_pdf
from preflight.ingest.soa import _day_from_name, _window, extract_soa

GRID = [
    ["Procedure", "Screening", "Cycle 1 Day 1", "Cycle 2 Day 1", "Week 12", "EOT"],
    ["Window (days)", "", "", "±3", "±7", ""],
    ["Informed consent", "X", "", "", "", ""],
    ["Vital signs a", "X", "X", "X", "X", "X"],
    ["Tumor imaging", "X", "", "", "X", ""],
]


def make_soa_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=792, height=612)
    page.insert_text((72, 50), "Treatment is given in 21-day cycles.", fontsize=10)
    x0, y0, cw, rh = 60, 80, 110, 22
    for r, row in enumerate(GRID):
        for c, text in enumerate(row):
            rect = pymupdf.Rect(x0 + c * cw, y0 + r * rh, x0 + (c + 1) * cw, y0 + (r + 1) * rh)
            page.draw_rect(rect, color=(0, 0, 0), width=0.7)
            if text:
                page.insert_text((rect.x0 + 4, rect.y1 - 7), text, fontsize=9)
    page.insert_text((72, 300), "x x x x x x x x", fontsize=9)
    doc.save(path)


def test_extract_soa_from_grid(tmp_path):
    path = str(tmp_path / "soa.pdf")
    make_soa_pdf(path)
    soa = extract_soa(path, read_pdf(path))
    assert [v.name for v in soa.visits] == ["Screening", "Cycle 1 Day 1", "Cycle 2 Day 1", "Week 12", "EOT"]
    assert [v.study_day for v in soa.visits] == [None, 1.0, 22.0, 85.0, None]
    assert (soa.visits[3].window_minus, soa.visits[3].window_plus) == (7.0, 7.0)
    names = {p.id: p.name for p in soa.procedures}
    assert sorted(names.values()) == ["Informed consent", "Tumor imaging", "Vital signs"]
    imaging = next(pid for pid, n in names.items() if n == "Tumor imaging")
    assert [soa.cells[v.id][imaging] for v in soa.visits] == [True, False, False, True, False]
    assert soa.span.page == 1 and len(soa.span.bbox) == 4


def test_day_and_window_parsing():
    assert _day_from_name("Cycles 7-17 Day 1", 21) == 127.0
    assert _day_from_name("C2/D8", 21) == 29.0
    assert _day_from_name("Visit 2 (Week 4)", None) == 29.0
    assert _day_from_name("Days -28 to -1", None) == -28.0
    assert _day_from_name("Cycle 3 Day 1", None) is None
    assert _window("+2") == (0.0, 2.0) and _window("±4") == (4.0, 4.0)
