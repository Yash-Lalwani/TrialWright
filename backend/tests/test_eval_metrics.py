# ruff: noqa: E501
from preflight.eval import metrics
from preflight.eval.types import TYPES


def issue(check, title, page, sev="major", quote=None, related=None):
    return {"check_id": check, "title": title, "severity": sev,
            "where": {"page": page, "quote": quote}, "related": related or []}


def err(t, page, **match):
    return {"error_id": "e", "type": t, "page": page, "match": match}


def test_types_cover_t01_to_t18_and_expected_checks():
    assert list(TYPES) == [f"T{n:02d}" for n in range(1, 19)]
    assert TYPES["T08"].expected_checks == ("C4",) and TYPES["T18"].expected_checks == ("C10",)


def test_tp_requires_expected_check_and_location():
    e = err("T06", 5)
    assert len(metrics.score_run([e], [issue("C4", "Minimum age disagrees", 5)], []).tp) == 1
    assert len(metrics.score_run([e], [issue("C9", "Minimum age disagrees", 5)], []).tp) == 0  # wrong check
    assert len(metrics.score_run([e], [issue("C4", "Minimum age disagrees", 9)], []).tp) == 0  # wrong place


def test_related_span_or_quote_counts_as_location():
    e = err("T08", 5, texts=["N = 420"])
    assert metrics.score_run([e], [issue("C4", "Sample size disagrees", 30, related=[{"page": 5}])], []).tp
    assert metrics.score_run([e], [issue("C4", "Sample size disagrees", 30, quote="we enrol N = 420 subjects")], []).tp


def test_each_flag_and_error_matched_once():
    es = [err("T06", 5), err("T06", 5)]
    s = metrics.score_run(es, [issue("C4", "Minimum age disagrees", 5)], [])
    assert (len(s.tp), len(s.fn), len(s.fp)) == (1, 1, 0)


def test_preexisting_flags_are_not_false_positives():
    real = issue("B1", "M11 4.5 is missing", None)
    s = metrics.score_run([err("T06", 5)], [issue("C4", "Minimum age disagrees", 5), real, issue("C6", "new thing", 8)], [real])
    assert (len(s.tp), len(s.fp)) == (1, 1) and s.fp[0]["check_id"] == "C6"


def test_advisory_excluded_and_aggregate_recall_precision():
    adv = issue("C9", "abbr", 1, sev="advisory")
    s = metrics.score_run([err("T06", 5), err("T07", 6)], [issue("C4", "Minimum age disagrees", 5), adv], [])
    agg = metrics.aggregate([s])
    assert agg["overall"] == {"recall": 0.5, "precision": 1.0, "f1": 0.667}
    assert {r["type"]: r["found"] for r in agg["by_type"]} == {"T06": 1, "T07": 0}


def test_false_alarms_count_critical_and_major_only():
    runs = [[issue("B1", "x", None, "major"), issue("B3", "y", 1, "minor")], [issue("C4", "z", 2, "critical")]]
    assert metrics.false_alarms_per_clean(runs) == 1.0


def test_shared_check_flags_are_matched_by_kind_not_order():
    """One C4 'ratio' flag must go to the ratio error, even though the sample-size error is listed first and shares its page."""
    es = [err("T08", 14, pages=[14, 19]), err("T10", 14)]
    s = metrics.score_run(es, [issue("C4", "Randomization ratio disagrees across sections: 2:1 vs 1:1", 14)], [])
    assert [e["type"] for e, _ in s.tp] == ["T10"] and [e["type"] for e in s.fn] == ["T08"]


def test_document_level_type_counts_a_new_flag_cited_on_another_page():
    """T09 changes the power sentence; C7 cites the sample-size statement elsewhere. A NEW C7 flag is a hit; one already in the clean run is not."""
    err = {"error_id": "e1", "type": "T09", "page": 11, "new": "80", "match": {"pages": [11]}}
    flag = {"check_id": "C7", "severity": "major", "title": "Stated sample size 100 cannot be reproduced (needs 130)", "where": {"page": 6}, "related": []}
    assert len(metrics.score_run([err], [flag], []).tp) == 1
    assert len(metrics.score_run([err], [flag], [flag]).tp) == 0


def test_check_agnostic_scoring_needs_the_edit_not_just_the_page():
    err = {"error_id": "e1", "type": "T06", "page": 8, "new": "21", "match": {"pages": [8], "texts": ["Age >= 21 years at time"]}}
    base = {"check_id": "LLM", "severity": "major", "related": []}
    on_page_unrelated = {**base, "title": "Typo in header", "where": {"page": 8, "quote": "Protocol number"}}
    cites_edit = {**base, "title": "Age limit differs", "where": {"page": 8, "quote": "Age >= 21 years at time of consent"}}
    mentions_value = {**base, "title": "Minimum age 21 conflicts with 18 elsewhere", "where": {"page": 8, "quote": "inclusion"}}
    wrong_page = {**base, "title": "Age 21", "where": {"page": 30, "quote": "Age 21"}}
    for flag, hit in ((on_page_unrelated, 0), (cites_edit, 1), (mentions_value, 1), (wrong_page, 0)):
        assert len(metrics.score_run([err], [flag], [], check_agnostic=True).tp) == hit


def test_grounding_tolerates_footnote_letters_but_not_invented_text():
    from preflight.eval.ablation import grounded

    page = "Schedule of Activities\nPharmacokinetic Sampling n\nHematology and serum chemistry at each visit\nThe study drug is given every 3 weeks."
    assert grounded("Pharmacokinetic Samplingn", page) and grounded("serum chemistry at each visit", page)
    assert not grounded("Patients receive 600 mg of rescue medication daily.", page) and not grounded("", page)
