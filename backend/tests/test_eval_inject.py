import json

import pymupdf

from preflight.eval import inject
from preflight.eval.types import TYPES

BODY = [
    "Synopsis",
    "Inclusion: Age at least 18 years at time of consent.",
    "Approximately 100 subjects will be randomized 1:1 to nivolumab 240 mg IV every 2 weeks.",
    "The study provides 90% power to detect a difference.",
    "Participants must be 18 years of age or older. See Section 4.3.2 for details.",
    "A total of 100 subjects will be randomized 1:1; nivolumab 240 mg IV every 2 weeks is given.",
    "Dose: 240 mg IV once, and 240 mg IV on Day 1 of each cycle.",
]


def make_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    y = 90
    for line in BODY:
        page.insert_text((72, y), line, fontname="tiro", fontsize=11)
        y += 22
    doc.save(path)
    return str(path)


def run(tmp_path, types, seed=1):
    pdf = make_pdf(tmp_path / "NCT00000001_protocol.pdf")
    return inject.inject_file(pdf, str(tmp_path / "out"), seed, n_target=(12, 12), types=types, sections=[])


def test_edits_appear_in_the_output_pdf_and_key_verifies(tmp_path):
    key = run(tmp_path, ["T06", "T08", "T10", "T14"])
    assert {e["type"] for e in key["errors"]} == {"T06", "T08", "T10", "T14"}
    assert inject.verify_key(str(tmp_path / "out" / key["injected_pdf"]), key) == []
    text = pymupdf.open(str(tmp_path / "out" / key["injected_pdf"]))[0].get_text()
    assert "at least 21 years" in text and "99.3.2" in text and "2:1" in text  # glyphs and spacing survive


def test_only_one_place_changes_so_an_inconsistency_exists(tmp_path):
    key = run(tmp_path, ["T08"])
    new = key["errors"][0]["new"]
    text = pymupdf.open(str(tmp_path / "out" / key["injected_pdf"]))[0].get_text()
    assert text.count(new + " subjects") == 1 and "100 subjects" in text


def test_same_seed_same_errors_and_key_file_written(tmp_path):
    a = run(tmp_path / "a" if (tmp_path / "a").mkdir() is None else tmp_path, ["T06", "T07", "T08"], seed=7)
    b = run(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path, ["T06", "T07", "T08"], seed=7)
    strip = lambda k: [(e["type"], e["original"], e["new"]) for e in k["errors"]]  # noqa: E731
    assert strip(a) == strip(b)
    assert json.loads((tmp_path / "a" / "out" / "NCT00000001_s7.json").read_text())["errors"]


def test_skips_are_recorded_with_a_reason(tmp_path):
    key = run(tmp_path, ["T11", "T16"])
    assert {s["type"] for s in key["skipped"]} >= {"T11", "T16"}
    assert all(s["reason"] for s in key["skipped"])


def test_every_injector_type_is_in_the_taxonomy():
    assert set(inject.INJECTORS) | set(inject.NOT_YET) == set(TYPES) and not set(inject.INJECTORS) & set(inject.NOT_YET)


def test_a_repeated_type_never_changes_every_mention(tmp_path):
    """Two mentions of the same value: after injecting twice one original must remain, or no inconsistency exists."""
    key = run(tmp_path, ["T08"], seed=3)
    key2 = inject.inject_file(str(tmp_path / "NCT00000001_protocol.pdf"), str(tmp_path / "rep"), 3, n_target=(12, 12),
                              types=["T08"], sections=[], max_per_type=3)
    text = pymupdf.open(str(tmp_path / "rep" / key2["injected_pdf"]))[0].get_text()
    assert len(key["errors"]) == 1 and len(key2["errors"]) == 1
    assert "100 subjects" in text  # an untouched original mention is still there


def _tight_pdf(path):
    """Lines 11.5pt apart at 12pt: a full-height redaction rectangle on one line also hits its neighbours."""
    doc = pymupdf.open()
    page = doc.new_page()
    lines = ["The study will enroll approximately 100 subjects. A subject is enrolled when they have",
             "received the first dose of study treatment.",
             "A total of 100 subjects will be randomized 1:1 and a sample size of 69 achieves 90% power",
             "2-sided exact test with a significance level of 0.05, assuming that the null hypothesis"]
    for n, t in enumerate(lines):
        page.insert_text((72, 100 + 11.5 * n), t, fontname="tiro", fontsize=12)
    doc.save(path)
    return str(path)


def test_edit_never_deletes_neighbouring_lines_in_tight_text(tmp_path):
    pdf = _tight_pdf(tmp_path / "NCT00000001_protocol.pdf")
    key = inject.inject_file(pdf, str(tmp_path / "out"), 1, n_target=(12, 12), types=["T09"], sections=[])
    assert key["errors"]
    out = str(tmp_path / "out" / key["injected_pdf"])
    assert inject.verify_key(out, key, pdf) == []
    text = pymupdf.open(out)[0].get_text()
    assert "received the first dose" in text and "significance level of 0.05" in text


def test_collateral_check_catches_a_full_height_rectangle(tmp_path, monkeypatch):
    """Mutation test: with the old full-height rectangle the checker must report the lost neighbour lines."""
    pdf = _tight_pdf(tmp_path / "NCT00000001_protocol.pdf")
    monkeypatch.setattr(inject.Ctx, "_band", lambda self, ln: pymupdf.Rect(ln["rect"].x0, ln["rect"].y0 + 0.4,
                                                                           ln["rect"].x1, ln["rect"].y1 - 0.4))
    key = inject.inject_file(pdf, str(tmp_path / "out"), 1, n_target=(12, 12), types=["T09"], sections=[])
    problems = inject.verify_key(str(tmp_path / "out" / key["injected_pdf"]), key, pdf)
    assert any("collateral loss" in p for p in problems)
