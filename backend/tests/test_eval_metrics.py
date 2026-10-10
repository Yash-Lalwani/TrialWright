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
    assert len(metrics.score_run([e], [issue("C4", "age disagrees", 5)], []).tp) == 1
    assert len(metrics.score_run([e], [issue("C9", "age disagrees", 5)], []).tp) == 0  # wrong check
    assert len(metrics.score_run([e], [issue("C4", "age disagrees", 9)], []).tp) == 0  # wrong place


def test_related_span_or_quote_counts_as_location():
    e = err("T08", 5, texts=["N = 420"])
    assert metrics.score_run([e], [issue("C4", "x", 30, related=[{"page": 5}])], []).tp
    assert metrics.score_run([e], [issue("C4", "x", 30, quote="we enrol N = 420 subjects")], []).tp


def test_each_flag_and_error_matched_once():
    es = [err("T06", 5), err("T06", 5)]
    s = metrics.score_run(es, [issue("C4", "a", 5)], [])
    assert (len(s.tp), len(s.fn), len(s.fp)) == (1, 1, 0)


def test_preexisting_flags_are_not_false_positives():
    real = issue("B1", "M11 4.5 is missing", None)
    s = metrics.score_run([err("T06", 5)], [issue("C4", "a", 5), real, issue("C6", "new thing", 8)], [real])
    assert (len(s.tp), len(s.fp)) == (1, 1) and s.fp[0]["check_id"] == "C6"


def test_advisory_excluded_and_aggregate_recall_precision():
    adv = issue("C9", "abbr", 1, sev="advisory")
    s = metrics.score_run([err("T06", 5), err("T07", 6)], [issue("C4", "a", 5), adv], [])
    agg = metrics.aggregate([s])
    assert agg["overall"] == {"recall": 0.5, "precision": 1.0, "f1": 0.667}
    assert {r["type"]: r["found"] for r in agg["by_type"]} == {"T06": 1, "T07": 0}


def test_false_alarms_count_critical_and_major_only():
    runs = [[issue("B1", "x", None, "major"), issue("B3", "y", 1, "minor")], [issue("C4", "z", 2, "critical")]]
    assert metrics.false_alarms_per_clean(runs) == 1.0
