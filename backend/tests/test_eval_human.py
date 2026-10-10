# ruff: noqa: E501
import json

import pymupdf

from preflight.eval import human
from tests.test_eval_bench import corpus


def kit(tmp_path):
    d = corpus(tmp_path)
    return human.build_kit("NCT00000001", tmp_path / "kit", d, minimum=4, maximum=6)


def test_kit_has_participant_files_and_a_private_key(tmp_path, monkeypatch):
    from preflight.eval import inject
    monkeypatch.setattr(inject, "_sections", lambda pdf: [])
    key = kit(tmp_path)
    part = tmp_path / "kit" / "participant"
    assert {p.name for p in part.iterdir()} == {"Protocol_for_review.pdf", "Answer_form.pdf", "Instructions.txt"}
    assert len(pymupdf.open(part / "Answer_form.pdf")) == 1                       # one-page form
    assert json.loads((tmp_path / "kit" / "key" / "answer_key.json").read_text())["errors"] == key["errors"]
    assert "answer" not in (part / "Instructions.txt").read_text().lower().replace("answer form", "")
    assert not (tmp_path / "kit" / "_work").exists()


def test_scoring_matches_by_page_once_and_counts_extras(tmp_path, monkeypatch):
    from preflight.eval import inject
    monkeypatch.setattr(inject, "_sections", lambda pdf: [])
    key = kit(tmp_path)
    page = key["errors"][0]["page"]
    s = human.score_participant(key, [{"page": page, "text": "x"}, {"page": page, "text": "same again"},
                                      {"page": 999, "text": "nothing here"}])
    assert s["found"] == min(2, sum(1 for e in key["errors"] if page in e["match"]["pages"])) and s["extra_findings"] >= 1
    assert human.score_participant(key, [])["found"] == 0


def test_summary_reports_every_participant(tmp_path, monkeypatch):
    from preflight.eval import inject
    monkeypatch.setattr(inject, "_sections", lambda pdf: [])
    key = kit(tmp_path)
    out = human.summarize(key, [{"id": "H1", "findings": []}, {"id": "H2", "findings": [{"page": 1, "text": "x"}]}],
                          {"found": 3, "seconds": 90})
    assert [p["id"] for p in out["participants"]] == ["H1", "H2"] and out["total_errors"] == len(key["errors"])
    assert out["preflight"]["found"] == 3
