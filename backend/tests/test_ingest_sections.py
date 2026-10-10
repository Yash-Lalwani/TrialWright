import pymupdf

from preflight.ingest.pdf import read_pdf
from preflight.ingest.sections import find_sections


def make_pdf(path):
    doc = pymupdf.open()

    def page(rows):
        p = doc.new_page()
        p.insert_text((72, 40), "Protocol XYZ-123 Version 2", fontsize=9)
        y = 90
        for text, bold, size in rows:
            p.insert_text((72, y), text, fontsize=size, fontname="hebo" if bold else "helv")
            y += size + 4
        return p

    page([("TABLE OF CONTENTS", True, 14)] + [(f"{n} Entry ........ {n + 3}", False, 11) for n in range(1, 8)])
    page([("1 INTRODUCTION", True, 12), ("Body text about the disease.", False, 11),
          ("1.1 Background", True, 12), ("More body text.", False, 11)])
    page([("2 OBJECTIVES AND ENDPOINTS FOR THE", True, 12), ("RANDOMIZED PART", True, 12),
          ("The primary objective is ORR at Week 24.", False, 11),
          ("5. Patients must sign consent", True, 11),
          ("2.1 Primary Objective", True, 12), ("ORR per RECIST 1.1.", False, 11)])
    doc.save(path)


def test_sections_from_synthetic_pdf(tmp_path):
    path = str(tmp_path / "p.pdf")
    make_pdf(path)
    doc = read_pdf(path)
    assert not any("Protocol XYZ" in ln.text for ln in doc.lines)

    secs = find_sections(doc)
    titles = [s.title for s in secs]
    assert titles == ["1 INTRODUCTION", "1.1 Background",
                      "2 OBJECTIVES AND ENDPOINTS FOR THE RANDOMIZED PART", "2.1 Primary Objective"]
    assert [s.level for s in secs] == [1, 2, 1, 2]
    two = secs[2]
    assert (two.page_start, two.page_end) == (3, 3)
    assert "5. Patients must sign consent" in two.text
