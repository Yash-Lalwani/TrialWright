# ruff: noqa: E501
import pytest

from preflight.burden import burden, costs
from preflight.burden.models import PeerPercentiles
from preflight.graph.models import Procedure, SoA, Visit
from tests.test_checks import graph, orr, span

VERSION, ROWS = costs.load()
ROW = {r.name: r for r in ROWS}
OVER = ROW[costs.VISIT_OVERHEAD]


def soa_of(visits, procs, marks):
    """marks: {visit_id: [procedure names]}"""
    vs = [Visit(id=f"v{i}", name=n, study_day=d, window_minus=None, window_plus=None) for i, (n, d) in enumerate(visits)]
    ps = [Procedure(id=f"p{i}", name=n, normalized_name=n.lower()) for i, n in enumerate(procs)]
    cells = {f"v{i}": {f"p{j}": procs[j] in marks.get(visits[i][0], []) for j in range(len(procs))} for i in range(len(visits))}
    return SoA(visits=vs, procedures=ps, cells=cells, span=span(14))


def test_totals_equal_the_sum_of_cost_rows_plus_visit_overhead():
    soa = soa_of([("Screening", -28), ("W1D1", 1), ("W2D1", 8)], ["Informed Consentx", "Tumor Biopsyq", "Vital Signsh"],
                 {"Screening": ["Informed Consentx", "Tumor Biopsyq"], "W1D1": ["Vital Signsh"], "W2D1": ["Vital Signsh"]})
    rep = burden.compute(graph(soa=soa))
    pat = 3 * OVER.patient_minutes + ROW["informed consent"].patient_minutes + ROW["tumor biopsy"].patient_minutes + 2 * ROW["vital signs"].patient_minutes
    site = 3 * OVER.site_minutes + ROW["informed consent"].site_minutes + ROW["tumor biopsy"].site_minutes + 2 * ROW["vital signs"].site_minutes
    cost = 3 * OVER.cost_usd + ROW["informed consent"].cost_usd + ROW["tumor biopsy"].cost_usd + 2 * ROW["vital signs"].cost_usd
    p = rep.per_patient
    assert (p.visits, p.procedures_total, p.invasive) == (3, 4, 1)               # only the biopsy is invasive
    assert p.patient_hours == round(pat / 60, 1) and p.site_hours == round(site / 60, 1) and p.cost_usd == round(cost)
    assert rep.assumptions.version == VERSION and rep.coverage.matched == rep.coverage.procedures == 3


def test_phone_visits_get_no_clinic_overhead_and_by_visit_uses_clean_labels():
    soa = soa_of([("W2D1 ± 2d 2", 8), ("Long-Term Survival Follow-Up Phone Call", 400)], ["Vital Signsh", "Telephone follow"],
                 {"W2D1 ± 2d 2": ["Vital Signsh"], "Long-Term Survival Follow-Up Phone Call": ["Telephone follow"]})
    rep = burden.compute(graph(soa=soa))
    assert [v.visit for v in rep.by_visit][0] == "W2D1"
    assert rep.by_visit[0].patient_minutes == round(OVER.patient_minutes + ROW["vital signs"].patient_minutes)
    assert rep.by_visit[1].patient_minutes == round(ROW["telephone follow-up"].patient_minutes)   # no overhead


def test_unmatched_procedures_are_reported_not_hidden_and_recurring_columns_counted():
    soa = soa_of([("Q3W (W10, W13, etc.)", 70), ("W1D1", 1)], ["Quarterly team lunch", "Vital Signsh"],
                 {"Q3W (W10, W13, etc.)": ["Quarterly team lunch", "Vital Signsh"], "W1D1": ["Vital Signsh"]})
    c = burden.compute(graph(soa=soa)).coverage
    assert c.unmatched == ["Quarterly team lunch"] and c.matched == 1 and c.recurring_columns == 1


def test_no_soa_gives_zero_report_and_neutral_score():
    rep = burden.compute(graph(soa=None))
    assert rep.per_patient.visits == 0 and rep.coverage.columns == 0 and burden.score(rep) == burden.NEUTRAL


def test_visit_label_cleaning():
    assert burden.visit_label("W1D1 n/a 1 SC/IT 1") == "W1D1"
    assert burden.visit_label("Screening (Day -30 to Day -1) n/a") == "Screening (Day -30 to Day -1)"
    assert burden.visit_label("End of Treatment") == "End of Treatment"


def test_score_is_100_minus_half_the_weighted_percentile_and_neutral_without_peers():
    rep = burden.compute(graph(soa=None))
    assert burden.score(rep) == 50.0
    rep = rep.model_copy(update={"peer_percentiles": PeerPercentiles(patient_hours=80, procedures_total=60, visits=40, n_peers_with_soa=20)})
    assert burden.score(rep) == pytest.approx(100 - 0.5 * (0.5 * 80 + 0.3 * 60 + 0.2 * 40))
    light = rep.model_copy(update={"peer_percentiles": PeerPercentiles(patient_hours=0, procedures_total=0, visits=0, n_peers_with_soa=20)})
    assert burden.score(light) == 100.0
    heavy = rep.model_copy(update={"peer_percentiles": PeerPercentiles(patient_hours=100, procedures_total=100, visits=100, n_peers_with_soa=20)})
    assert burden.score(heavy) == 50.0


def test_orphans_come_from_a_c2_check():
    soa = soa_of([("W1D1", 1)], ["Exploratory skin biopsy", "Vital Signsh"], {"W1D1": ["Exploratory skin biopsy", "Vital Signsh"]})
    ep, obj = orr([24])
    assert burden.compute(graph(soa=soa)).orphan_procedures == []                  # C2 needs extracted endpoints
    rep = burden.compute(graph(soa=soa, endpoints=[ep], objectives=[obj]))
    assert [o.name for o in rep.orphan_procedures] == ["Exploratory skin biopsy"]
    assert rep.orphan_procedures[0].occurrences == 1 and rep.orphan_procedures[0].cost_usd == round(ROW["tumor biopsy"].cost_usd)
