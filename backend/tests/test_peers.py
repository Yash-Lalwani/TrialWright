# ruff: noqa: E501
from preflight.burden import peers
from preflight.burden.models import PeerQuery
from preflight.graph.models import Criterion
from tests.test_checks import graph, span

Q = PeerQuery(condition="Melanoma", phase="PHASE2", start_year_min=2015)
TEXT = """Inclusion Criteria:

* Age 18 or older
* ECOG 0-1
* Measurable disease

Exclusion Criteria:

* Prior therapy
* Active infection
"""


def study(nct, enroll=100, n_out=(1, 3), arms=2, inc_n=3, minage="18 Years", start="2020-01", end="2022-01"):
    crit = "Inclusion Criteria:\n" + "".join(f"* c{i}\n" for i in range(inc_n)) + "Exclusion Criteria:\n* x\n"
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": f"Study {nct}"},
        "statusModule": {"startDateStruct": {"date": start}, "primaryCompletionDateStruct": {"date": end}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
        "designModule": {"phases": ["PHASE2"], "enrollmentInfo": {"count": enroll}},
        "armsInterventionsModule": {"armGroups": [{"label": "a"}] * arms},
        "outcomesModule": {"primaryOutcomes": [{"measure": "m"}] * n_out[0], "secondaryOutcomes": [{"measure": "s"}] * n_out[1]},
        "eligibilityModule": {"eligibilityCriteria": crit, "minimumAge": minage}}}


def test_parse_criteria_counts_bullets_per_section():
    assert peers.parse_criteria(TEXT) == (3, 2)
    assert peers.parse_criteria("Inclusion Criteria:\nAdults\nWith disease\n") == (2, None)   # no bullets: count lines
    assert peers.parse_criteria(None) == (None, None) and peers.parse_criteria("") == (None, None)


def test_age_and_duration_parsing():
    assert peers.years("18 Years") == 18 and peers.years("6 Months") == 0.5 and peers.years("N/A") is None
    v = peers.peer_values(study("NCT1", start="2020-01", end="2022-01"))
    assert v["duration_months"] == 24 and v["n_arms"] == 2 and v["n_secondary_outcomes"] == 3 and v["min_age"] == 18


def test_percentile_is_mid_rank():
    assert peers.percentile(5, [1, 2, 3, 4]) == 100.0
    assert peers.percentile(0, [1, 2, 3, 4]) == 0.0
    assert peers.percentile(5, [5, 5, 5, 5]) == 50.0          # equal to every peer: the middle, not the top
    assert peers.percentile(3, [1, 2, 3, 4]) == 62.5          # 2 below + half of 1 equal = 2.5 of 4


def make_peers(n=10):
    return [study(f"NCT{i:08d}", enroll=100 + 10 * i, inc_n=2 + i % 4) for i in range(n)]


def test_build_peer_set_percentiles_and_distribution_match_hand_calculation():
    ps = peers.build_peer_set({"enrollment": 145.0, "n_inclusion_criteria": None}, make_peers(10), Q)
    m = {x.metric: x for x in ps.metrics}
    assert ps.n == 10 and "n_inclusion_criteria" not in m         # protocol value missing: metric omitted, not invented
    e = m["enrollment"]
    assert e.distribution == [100.0 + 10 * i for i in range(10)] and e.peer_median == 145.0
    assert e.percentile == 50.0                                    # 100..140 is 5 of 10 below 145, none equal
    assert e.peer_p25 == 122.5 and e.peer_p75 == 167.5
    assert len(ps.trials) == 10 and ps.trials[0].sponsor == "Sponsor" and ps.hotspot_issue_ids == []


def test_own_study_is_excluded_and_too_few_peers_gives_none():
    own = make_peers(10)[3]["protocolSection"]["identificationModule"]["nctId"]
    assert peers.build_peer_set({"enrollment": 1.0}, make_peers(10), Q, own_nct=own).n == 9
    assert peers.build_peer_set({"enrollment": 1.0}, make_peers(7), Q) is None


def test_protocol_values_come_from_the_graph_only_when_present():
    from preflight.graph.models import Endpoint, Objective
    g = graph()
    v0 = peers.protocol_values(g)
    assert v0["n_arms"] == 2 and v0["min_age"] == 18 and v0["n_inclusion_criteria"] is None and v0["enrollment"] is None
    ep = Endpoint(id="e1", text="ORR", measure="ORR", timepoints_weeks=[], analysis_ids=[], span=span())
    obj = Objective(id="o1", level="primary", text="x", endpoint_ids=["e1"], span=span())
    cr = [Criterion(id=f"c{i}", kind="inclusion" if i < 3 else "exclusion", text="t", thresholds=[], span=span()) for i in range(5)]
    v = peers.protocol_values(graph(endpoints=[ep], objectives=[obj], criteria=cr))
    assert (v["n_primary_outcomes"], v["n_inclusion_criteria"], v["n_exclusion_criteria"]) == (1, 3, 2)


def test_phase_normalisation_and_find_never_raises(monkeypatch):
    assert peers.normalise_phase("PHASE2") == "PHASE2" and peers.normalise_phase("Phase 3") == "PHASE3" and peers.normalise_phase(None) is None
    assert peers.find(graph()) is None                                  # no condition known: None, no network
    async def boom(*a, **k):
        raise RuntimeError("offline")
    monkeypatch.setattr(peers.client, "search_peers", boom)
    g = graph()
    g.meta.condition = "Melanoma"
    assert peers.find(g) is None                                        # failure degrades to None


def test_broaden_drops_leading_words_and_keeps_the_original_first():
    out = peers.broaden("Moderate to Severe Atopic Hand and Foot Dermatitis")
    assert out[0] == "Moderate to Severe Atopic Hand and Foot Dermatitis" and out[-1] == "Dermatitis"
    assert "Hand and Foot Dermatitis" in out and "Atopic Hand and Foot Dermatitis" in out
    assert peers.broaden("KRAS p, G12c Mutated /Advanced Metastatic NSCLC")[-1] == "NSCLC"
    assert peers.broaden("Melanoma") == ["Melanoma"]


def test_search_broadens_until_enough_peers_and_reports_the_query_used(monkeypatch):
    asked = []

    async def fake_search(cond, phase, year, limit, fields=None):
        asked.append(cond)
        n = {"Dermatitis": 60}.get(cond, 1)
        return [study(f"NCT{i:08d}") for i in range(n)] if fields != "NCTId" else [{"x": 1}] * n

    async def fake_study(nct):
        return {"protocolSection": {"conditionsModule": {"conditions": ["Atopic Hand Dermatitis"]}}}

    monkeypatch.setattr(peers.client, "search_peers", fake_search)
    monkeypatch.setattr(peers.client, "get_study", fake_study)
    g = graph()
    g.meta.nct_id, g.meta.phase = "NCT99999999", "PHASE3"
    ps = peers.find(g)
    assert ps is not None and ps.query.condition == "Dermatitis" and ps.query.phase == "PHASE3" and ps.n >= 50
    assert asked[0] == "Atopic Hand Dermatitis"                       # the registry's own wording is tried first
