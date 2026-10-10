import csv
import io

import pymupdf

COLUMNS = ["id", "severity", "category", "check_id", "source", "status", "page", "section", "title", "quote",
           "explanation", "standard_ref", "fix"]


def _row(i: dict) -> dict:
    w, why, fix = i.get("where") or {}, i.get("why") or {}, i.get("fix") or {}
    return {"id": i["id"], "severity": i["severity"], "category": i["category"], "check_id": i["check_id"],
            "source": i["source"], "status": i["status"], "page": w.get("page"), "section": w.get("section"),
            "title": i["title"], "quote": w.get("quote"), "explanation": why.get("explanation"),
            "standard_ref": why.get("standard_ref"), "fix": fix.get("suggestion")}


def to_csv(issues: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(_row(i) for i in issues)
    return buf.getvalue().encode()


def to_pdf(title: str, run: dict, issues: list[dict]) -> bytes:
    """Plain issue report: header, score, then one block per issue."""
    doc = pymupdf.open()
    width, height, margin = 595, 842, 50
    page, y = doc.new_page(width=width, height=height), margin

    def write(text: str, size: float = 9.5, bold: bool = False, gap: float = 4):
        nonlocal page, y
        font = "hebo" if bold else "helv"
        for attempt in range(2):
            if y > height - margin - size * 2:
                page, y = doc.new_page(width=width, height=height), margin
            left = page.insert_textbox(pymupdf.Rect(margin, y, width - margin, height - margin), text,
                                       fontsize=size, fontname=font)
            if left >= 0 or attempt:
                break
            y = height  # did not fit: retry on a new page
        y = height - margin - max(left, 0) + gap

    s = run.get("score") or {}
    write("Protocol Pre-Flight issue report", 16, True, 8)
    write(title, 11, True)
    write(f"Run {run['run_id']} ({run['mode']}), {run.get('finished_at') or ''}")
    write(f"Pre-Flight Score {s.get('overall')}  |  Completeness {s.get('completeness')}  Consistency "
          f"{s.get('consistency')}  Burden {s.get('burden')}  Amendment risk {s.get('amendment_risk')}", 10, True, 10)
    write("Pre-Flight assists protocol authors. It does not approve protocols.", 8.5, gap=12)
    for i in map(_row, issues):
        write(f"{i['id']}  [{i['severity'].upper()}]  {i['title']}", 10, True, 2)
        write(f"{i['check_id']} · {i['category']} · {i['source']} · page {i['page'] or '-'} · {i['section'] or ''} · "
              f"status {i['status']}", 8.5, gap=2)
        if i["quote"]:
            write(f"“{i['quote']}”", 8.5, gap=2)
        write(f"Why: {i['explanation']}" + (f" ({i['standard_ref']})" if i["standard_ref"] else ""), 9, gap=2)
        if i["fix"]:
            write(f"Fix: {i['fix']}", 9, gap=10)
    return doc.tobytes()
