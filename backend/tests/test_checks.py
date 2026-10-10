from preflight.checks.registry import CheckContext, discover
from preflight.graph.models import (Criterion, Endpoint, Meta, NumberFact, Objective, Procedure, ProtocolGraph,
                                    Section, SoA, Span, Stats, Visit)
from preflight.pipeline import check_graph
from preflight.score import compute

CHECKS = discover()
CTX = CheckContext()


def span(page=1, quote="q"):
    return Span(page=page, bbox=[72, 100, 540, 112], quote=quote)


def graph(**kw) -> ProtocolGraph:
    base = dict(
        protocol_id="prt_t",
        meta=Meta(title="T", nct_id=None, phase="PHASE3", condition=None, sponsor=None, masking="NONE",
                  allocation="RANDOMIZED", n_arms=2, ratio="1:1"),
        sections=[], objectives=[], endpoints=[], criteria=[], min_age=18, max_age=None, arms=[], soa=None,
        stats=Stats(sample_size=None, alpha=None, sided=None, power=None, effect_size=None, effect_type=None,
                    control_rate=None, dropout=None, analyses=[]),
        numbers=[], xrefs=[], abbreviations={"defined": {}, "used": []},
    )
    base.update(kw)
    return ProtocolGraph(**base)


def soa(cells):
    visits = [Visit(id="v1", name="Screening", study_day=-28, window_minus=None, window_plus=None),
              Visit(id="v2", name="Week 12", study_day=85, window_minus=3, window_plus=3),
              Visit(id="v3", name="Week 25", study_day=176, window_minus=7, window_plus=7)]
    procs = [Procedure(id="p1", name="Tumor imaging (CT/MRI)", normalized_name="tumor imaging ct mri"),
             Procedure(id="p2", name="Vital signs", normalized_name="vital signs"),
             Procedure(id="p3", name="Exploratory skin biopsy", normalized_name="exploratory skin biopsy")]
    return SoA(visits=visits, procedures=procs, cells=cells, span=span(14))


def run(check_id, g):
    return CHECKS[check_id].fn(g, CTX)


def orr(weeks):
    ep = Endpoint(id="ep_1", text="ORR per RECIST 1.1", measure="ORR", timepoints_weeks=weeks,
                  analysis_ids=[], span=span(21))
    obj = Objective(id="obj_1", level="primary", text="Compare ORR", endpoint_ids=["ep_1"], span=span(21))
    return ep, obj


def test_c1_missing_visit_and_missing_procedure():
    ep, obj = orr([24])
    cells = {"v1": {"p1": True}, "v2": {"p1": True}, "v3": {"p1": False}}
    out = run("C1", graph(endpoints=[ep], objectives=[obj], soa=soa(cells)))
    assert len(out) == 1 and out[0].severity == "critical" and "Week 25" in out[0].why.explanation

    ep, obj = orr([12])
    out = run("C1", graph(endpoints=[ep], objectives=[obj], soa=soa({"v2": {"p1": False}})))
    assert "not collected" in out[0].title and out[0].fix.patch["op"] == "set_soa_cell"

    out = run("C1", graph(endpoints=[ep], objectives=[obj], soa=soa({"v2": {"p1": True}})))
    assert out == []


def test_c2_orphan_procedure():
    ep, obj = orr([12])
    out = run("C2", graph(endpoints=[ep], objectives=[obj], soa=soa({"v2": {"p1": True, "p3": True}})))
    assert [i.title.split("'")[1] for i in out] == ["Exploratory skin biopsy"]


def test_c3_objective_without_endpoint_and_endpoint_without_analysis():
    ep, _ = orr([12])
    lonely = Objective(id="obj_2", level="secondary", text="Assess QoL", endpoint_ids=[], span=span(22))
    obj = Objective(id="obj_1", level="primary", text="Compare ORR", endpoint_ids=["ep_1"], span=span(21))
    stats = graph().stats.model_copy(update={"analyses": [{"id": "ana_1", "endpoint_id": None, "method": "x",
                                                            "span": span(40).model_dump()}]})
    out = run("C3", graph(objectives=[obj, lonely], endpoints=[ep], stats=stats))
    assert sorted(i.title for i in out) == ["Endpoint 'ORR' has no analysis method in the statistics section",
                                           "Secondary objective has no endpoint"]


def test_c4_number_disagreement_ignores_per_arm_counts():
    nums = [NumberFact(kind="age_max", value=75.0, unit="years", span=span(5)),
            NumberFact(kind="age_max", value=75.0, unit="years", span=span(23)),
            NumberFact(kind="age_max", value=80.0, unit="years", span=span(24)),
            NumberFact(kind="sample_size", value=226.0, unit=None, span=span(45, "approximately 226 participants")),
            NumberFact(kind="sample_size", value=113.0, unit=None, span=span(45, "Arm A: approximately 113"))]
    out = run("C4", graph(numbers=nums))
    assert len(out) == 1 and out[0].where.page == 24 and "80" in out[0].title


def test_c5_blinded_without_unblinding():
    meta = graph().meta.model_copy(update={"masking": "DOUBLE"})
    sec = Section(id="s", m11_id="4.1", title="4.1 Design", level=2, page_start=10, page_end=10,
                  text="This is a double-blind study.")
    assert run("C5", graph(meta=meta, sections=[sec]))[0].severity == "critical"
    sec2 = sec.model_copy(update={"text": "Emergency unblinding is done through the IxRS."})
    assert run("C5", graph(meta=meta, sections=[sec, sec2])) == []


def test_c6_overlapping_windows():
    s = soa({}).model_copy(update={"visits": [
        Visit(id="v1", name="Week 2", study_day=15, window_minus=3, window_plus=3),
        Visit(id="v2", name="Week 3", study_day=20, window_minus=3, window_plus=3)]})
    assert len(run("C6", graph(soa=s))) == 1


def test_c8_inclusion_exclusion_conflict_with_units():
    inc = Criterion(id="inc_1", kind="inclusion", text="Hb >= 9 g/dL", span=span(23),
                    thresholds=[{"test": "Hemoglobin", "op": ">=", "value": 9, "unit": "g/dL"}])
    exc = Criterion(id="exc_1", kind="exclusion", text="Hb < 100 g/L", span=span(25),
                    thresholds=[{"test": "hemoglobin", "op": "<", "value": 100, "unit": "g/L"}])
    out = run("C8", graph(criteria=[inc, exc]))
    assert len(out) == 1 and out[0].severity == "critical" and "between 9 and 10" in out[0].why.explanation
    ok = exc.model_copy(update={"thresholds": [{"test": "hemoglobin", "op": "<", "value": 90, "unit": "g/L"}]})
    assert run("C8", graph(criteria=[inc, ok])) == []


def test_c9_broken_xref_and_undefined_abbreviation():
    secs = [Section(id=f"s{n}", m11_id=None, title=f"{n} Title", level=1, page_start=n, page_end=n,
                    text="Assess ORR. ORR again. ORR thrice.") for n in range(1, 9)]
    xrefs = [{"text": "see Section 15", "target": "Section 15", "span": span(3).model_dump()},
             {"text": "see Section 4.2", "target": "Section 4.2", "span": span(3).model_dump()}]
    out = run("C9", graph(sections=secs, xrefs=xrefs, abbreviations={"defined": {}, "used": ["ORR"]}))
    titles = [i.title for i in out]
    assert "Cross-reference to Section 15, which does not exist" in titles
    assert not any("4.2" in t for t in titles)
    assert any("'ORR'" in t for t in titles)


def test_completeness_missing_and_score():
    secs = [Section(id="s1", m11_id="5.1", title="5.1 Inclusion Criteria", level=2, page_start=23, page_end=24,
                    text="word " * 60)]
    out = CHECKS["B1"].fn(graph(sections=secs), CTX)
    assert any("Protocol Synopsis" in i.title for i in out)
    assert not any("Inclusion Criteria" in i.title for i in out)

    issues = run("C4", graph(numbers=[NumberFact(kind="ratio", value="1:1", unit=None, span=span(5)),
                                      NumberFact(kind="ratio", value="1:1", unit=None, span=span(6)),
                                      NumberFact(kind="ratio", value="2:1", unit=None, span=span(7))]))
    s = compute(issues, present=8, thin=2, required=10, burden=50)
    assert (s.completeness, s.consistency, s.amendment_risk) == (90, 85, 100)
    assert s.overall == round(0.25 * 90 + 0.35 * 85 + 0.2 * 50 + 0.2 * 100)


async def test_check_graph_assigns_ids_and_sorts():
    ep, obj = orr([24])
    result = await check_graph(graph(endpoints=[ep], objectives=[obj], soa=soa({"v1": {"p1": True}})),
                               "rules_only")
    assert [i.id for i in result.issues][:2] == ["iss_01", "iss_02"]
    assert result.issues[0].severity == "critical"
    assert result.completeness.summary.required > 0
