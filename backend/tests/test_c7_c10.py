from preflight.checks.registry import CheckContext
from preflight.checks.sample_size import calc_sample_size, parse_ratio
from preflight.graph.models import Endpoint, NumberFact, Objective, Stats
from tests.test_checks import CHECKS, graph, span


def stats(**kw):
    base = dict(sample_size=None, alpha=0.05, sided=2, power=0.8, effect_size=None, effect_type=None, control_rate=None,
                dropout=None, analyses=[])
    base.update(kw)
    return Stats(**base)


def test_calculator_matches_textbook_values():
    assert calc_sample_size("mean_diff_sd", 0.5).n_per_arm_control == 64            # d=0.5, 80% power, alpha .05
    hr = calc_sample_size("hazard_ratio", 0.7, control_rate=0.6)
    assert hr.events == 247                                                          # Schoenfeld, HR 0.7, 1:1
    p = calc_sample_size("proportions", 0.27, control_rate=0.12)
    assert 95 <= p.n_per_arm_control <= 110
    assert calc_sample_size("proportions", 0.27, control_rate=0.12, dropout=0.1).n_total_enrolled > p.n_total_evaluable


def test_calculator_allocation_ratio_and_missing_inputs():
    one, two = calc_sample_size("mean_diff_sd", 0.5), calc_sample_size("mean_diff_sd", 0.5, ratio=2.0)
    assert two.n_total_evaluable > one.n_total_evaluable and parse_ratio("2:1") == 2.0 and parse_ratio("bad") == 1.0
    assert calc_sample_size("hazard_ratio", 0.7) is None and calc_sample_size("proportions", 0.3) is None


def run7(**kw):
    return CHECKS["C7"].fn(graph(stats=stats(**kw)), CheckContext())


def test_c7_flags_a_mismatch_and_accepts_a_reproducible_n():
    ok = calc_sample_size("mean_diff_sd", 0.5).n_total_evaluable
    assert run7(sample_size=ok, effect_type="mean_diff_sd", effect_size=0.5) == []
    assert run7(sample_size=ok + 2, effect_type="mean_diff_sd", effect_size=0.5) == []  # within 5%
    out = run7(sample_size=ok + 40, effect_type="mean_diff_sd", effect_size=0.5)
    assert len(out) == 1 and out[0].check_id == "C7" and "cannot be reproduced" in out[0].title


def test_c7_accepts_either_evaluable_or_enrolled_n_when_dropout_is_stated():
    c = calc_sample_size("mean_diff_sd", 0.5, dropout=0.1)
    for n in (c.n_total_evaluable, c.n_total_enrolled):
        assert run7(sample_size=n, effect_type="mean_diff_sd", effect_size=0.5, dropout=0.1) == []


def test_c7_silent_without_enough_inputs_and_minor_when_alpha_assumed():
    assert run7(sample_size=100, effect_type="mean_diff_sd") == []
    out = run7(sample_size=500, effect_type="mean_diff_sd", effect_size=0.5, alpha=None)
    assert out and out[0].severity == "minor" and "assumed" in out[0].why.explanation


def registry(**kw):
    ps = {"identificationModule": {"nctId": "NCT00000001"},
          "eligibilityModule": {"minimumAge": kw.get("min_age", "18 Years")},
          "designModule": {"enrollmentInfo": {"count": kw.get("count", 100), "type": kw.get("type", "ESTIMATED")}},
          "outcomesModule": {"primaryOutcomes": [{"measure": "ORR", "timeFrame": kw.get("tf", "Up to 24 weeks")}]}}
    return {"protocolSection": ps}


def run10(rec, **kw):
    return CHECKS["C10"].fn(graph(**kw), CheckContext(registry_record=rec))


def test_c10_min_age_mismatch_and_match():
    num = NumberFact(kind="age_min", value=21.0, unit="years", span=span(8, "Age 21 years"))
    out = run10(registry(), min_age=21, numbers=[num])
    assert len(out) == 1 and out[0].where.page == 8 and "registry" in out[0].title
    assert run10(registry(min_age="21 Years"), min_age=21, numbers=[num]) == []


def test_c10_enrollment_only_compared_when_registry_value_is_an_estimate():
    g = dict(stats=stats(sample_size=120), min_age=None)
    assert any("Enrollment" in i.title for i in run10(registry(count=100), **g))
    assert run10(registry(count=100, type="ACTUAL"), **g) == []
    assert run10(registry(count=120), **g) == []


def test_c10_primary_timeframe_and_no_record():
    ep = Endpoint(id="ep_1", text="ORR", measure="ORR", timepoints_weeks=[12.0], analysis_ids=[], span=span(21))
    obj = Objective(id="o1", level="primary", text="x", endpoint_ids=["ep_1"], span=span(21))
    out = run10(registry(), min_age=None, endpoints=[ep], objectives=[obj])
    assert [i.severity for i in out] == ["minor"] and "timepoint" in out[0].title
    assert run10(None, min_age=None) == []
