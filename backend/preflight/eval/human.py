# ruff: noqa: E501
"""Human baseline (N5): build the review kit and score participants with the same matching rule as Pre-Flight.

    build_kit("NCT03738423", out_dir)   -> out_dir/participant/{Protocol_for_review.pdf, Answer_form.pdf, Instructions.txt}
                                           out_dir/key/answer_key.json   (private: never share the key folder)
    score_participant(key, findings)    -> which injected errors a participant found
    summarize(key, participants, preflight) -> the `human_baseline` block of the benchmark results (CONTRACTS 4.12)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pymupdf

from . import inject

INSTRUCTIONS = """PROTOCOL REVIEW EXERCISE

You are reviewing a draft clinical trial protocol for internal errors, as you would before sending it to a review
committee. Errors have been planted in this copy: numbers that disagree between sections, references that point to
nothing, text that was removed, and similar problems. Real imperfections that were in the original document are
not part of the exercise. You are not told how many errors there are or what kinds.

TIME: 20 minutes, from the moment you open the PDF. Note the time you write down your first finding.

HOW TO RECORD
 - Use the answer form (one line per problem).
 - PAGE means the page number shown by your PDF viewer (its toolbar), NOT the number printed on the page.
 - WHAT IS WRONG: a few words, e.g. "minimum age is 21 here but 18 on page 39".
 - If you see the same problem in two places, list the page where you first noticed it.

RULES
 - Work alone. Do not search the internet or look up this trial; do not use AI tools.
 - You may use the PDF viewer's search, and paper or a calculator.
 - Stop at 20 minutes even if you are mid-section.

No personal data is collected. Your results are reported by participant number (H1, H2, ...), with the number of
problems found and the time taken.
"""


def _answer_form(path: Path, rows: int = 18) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((54, 60), "Protocol review: answer form", fontname="hebo", fontsize=16)
    page.insert_text((54, 82), "Participant: ______   Start time: ________   Time of first finding: ________   End: ________",
                     fontname="helv", fontsize=9.5)
    page.insert_text((54, 98), "PAGE = number shown by your PDF viewer. One problem per line.", fontname="helv", fontsize=9)
    y, x0, x1, xp = 118, 54, 558, 110
    page.insert_text((x0 + 4, y + 13), "#", fontname="hebo", fontsize=9)
    page.insert_text((x0 + 30, y + 13), "Page", fontname="hebo", fontsize=9)
    page.insert_text((xp + 10, y + 13), "What is wrong", fontname="hebo", fontsize=9)
    for n in range(rows + 1):
        yy = y + 20 + n * 34
        page.draw_line((x0, yy), (x1, yy), width=0.5)
        if n < rows:
            page.insert_text((x0 + 4, yy + 20), str(n + 1), fontname="helv", fontsize=9)
    page.draw_line((x0 + 26, y + 20), (x0 + 26, y + 20 + rows * 34), width=0.5)
    page.draw_line((xp, y + 20), (xp, y + 20 + rows * 34), width=0.5)
    doc.save(path)


def build_kit(nct: str, out_dir: str | Path, corpus_dir: str | Path, seed: int = 1, minimum: int = 10, maximum: int = 12,
              registry: dict | None = None) -> dict:
    """Inject until at least `minimum` errors land (trying seeds seed, seed+1, ...), then write the kit."""
    out = Path(out_dir)
    pdf = str(Path(corpus_dir) / f"{nct}_protocol.pdf")
    sections = inject._sections(pdf)
    tmp = out / "_work"
    key = None
    for s in range(seed, seed + 40):
        shutil.rmtree(tmp, ignore_errors=True)
        key = inject.inject_file(pdf, str(tmp), s, (minimum, maximum), registry, sections=sections, max_per_type=2)
        if len(key["errors"]) >= minimum and not inject.verify_key(str(tmp / key["injected_pdf"]), key, pdf):
            break
    else:
        raise RuntimeError(f"could not plant {minimum} verifiable errors in {nct}")
    part, priv = out / "participant", out / "key"
    part.mkdir(parents=True, exist_ok=True)
    priv.mkdir(parents=True, exist_ok=True)
    shutil.copy(tmp / key["injected_pdf"], part / "Protocol_for_review.pdf")
    _answer_form(part / "Answer_form.pdf")
    (part / "Instructions.txt").write_text(INSTRUCTIONS)
    (priv / "answer_key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False))
    shutil.rmtree(tmp)
    return key


def score_participant(key: dict, findings: list[dict]) -> dict:
    """findings: [{"page": int, "text": str}]. An injected error is found when a finding is on its page (or on the
    page of another mention of it); each finding and each error is used once (EVALUATION.md section 3)."""
    used: set[int] = set()
    found = []
    for e in key["errors"]:
        pages = set(e["match"].get("pages", [e["page"]]))
        hit = next((i for i, f in enumerate(findings) if i not in used and f["page"] in pages), None)
        if hit is not None:
            used.add(hit)
            found.append(e["error_id"])
    return {"found": len(found), "found_ids": found, "extra_findings": len(findings) - len(used)}


def summarize(key: dict, participants: list[dict], preflight: dict) -> dict:
    """participants: [{"id": "H1", "findings": [...], "minutes": 20, "first_finding_minutes": 3.5}];
    preflight: {"found": int, "seconds": float}. Every participant is reported, not only the mean."""
    rows = []
    for p in participants:
        s = score_participant(key, p["findings"])
        rows.append({"id": p["id"], "found": s["found"], "minutes": p.get("minutes", 20),
                     "first_finding_minutes": p.get("first_finding_minutes"), "extra_findings": s["extra_findings"]})
    return {"protocol": f"{key['nct_id']} (injected, {len(key['errors'])} errors)", "participants": rows,
            "preflight": preflight, "total_errors": len(key["errors"])}
