# ruff: noqa: E501
import importlib
from datetime import date
from unittest import mock

from preflight.burden import peers
from preflight.graph.models import Arm, Criterion, Endpoint, Objective, Section
from tests.test_checks import graph, span
from tests.test_peers import Q, study

# the package re-exports functions named hotspots/precedent, which shadow the submodules
hs = importlib.import_module("preflight.burden.hotspots")
pr = importlib.import_module("preflight.burden.precedent")
TODAY = date(2026, 10, 10)


def peer_studies(n=40):
    """exclusion counts 1..n via criteria text: study i has i exclusion bullets."""
    out = []
    for i in range(1, n + 1):
        s = study(f"NCT{i:08d}", enroll=100 + i, inc_n=3)
        s["protocolSection"]["eligibilityModule"]["eligibilityCriteria"] = "Inclusion Criteria:\n* a\n* b\n* c\nExclusion Criteria:\n" + "".join(f"* x{j}\n" for j in range(i))
        out.append(s)
    return out


def crit(kind, n):
    return [Criterion(id=f"c_{kind}{i}", kind=kind, text=f"{kind} {i}", thresholds=[], span=span(23 + (kind == "exclusion"), f"{kind} criterion {i}")) for i in range(n)]


def g_with(n_excl, **kw):
    return graph(criteria=crit("inclusion", 3) + crit("exclusion", n_excl),
                 sections=[Section(id="s1", m11_id="5.3", title="5.3 Exclusion Criteria", level=2, page_start=20, page_end=30, text="")], **kw)


def test_outlier_fires_with_real_peer_ids_and_normal_value_does_not():
    ps = peers.build_peer_set(peers.protocol_values(g_with(40)), peer_studies(), Q)
    with mock.patch.object(peers, "peer_studies", return_value=peer_studies()):
        hit = hs.hotspots(g_with(40), ps)
        quiet = hs.hotspots(g_with(20), peers.build_peer_set(peers.protocol_values(g_with(20)), peer_studies(), Q))
    assert quiet == []
    assert [i.check_id for i in hit] == ["D3"] and hit[0].category == "amendment_risk" and hit[0].severity == "major"   # 40 peers, p97+
    assert "40 exclusion criteria" in hit[0].title and hit[0].where.page == 24 and hit[0].where.section == "5.3 Exclusion Criteria"
    cited = [t.split()[0] for t in hit[0].why.explanation.split("Less restrictive peers: ")[1].rstrip(".").split(", ")]
    assert len(cited) == 3 and all(c.startswith("NCT0000") for c in cited)          # real ids from the peer records, nearest the median


def test_no_peers_no_hotspots_and_ties_do_not_fire():
    assert hs.hotspots(g_with(5), None) == []
    same = [study(f"NCT{i:08d}", inc_n=3) for i in range(1, 21)]
    ps = peers.build_peer_set({"enrollment": 100.0, "n_secondary_outcomes": 3.0}, same, Q)
    assert hs._fires(next(m for m in ps.metrics if m.metric == "n_secondary_outcomes"), "high", ps.n) is None


def test_severity_needs_enough_peers_for_major():
    ps = peers.build_peer_set(peers.protocol_values(g_with(17)), peer_studies(16), Q)
    m = next(x for x in ps.metrics if x.metric == "n_exclusion_criteria")
    assert hs._fires(m, "high", 16) == "minor" and hs._fires(m, "high", 40) == "major"


def test_precedent_ranks_by_similarity_excludes_self_and_caps_at_ten():
    ps = peers.build_peer_set({}, peer_studies(30), Q)
    arms = [Arm(name="nivolumab", type="experimental", dose=None, route=None, frequency=None, duration_weeks=None)]
    ep = Endpoint(id="e1", text="Objective response rate by week 24", measure="ORR", timepoints_weeks=[24], analysis_ids=[], span=span())
    obj = Objective(id="o1", level="primary", text="ORR", endpoint_ids=["e1"], span=span())
    g = graph(arms=arms, endpoints=[ep], objectives=[obj], criteria=crit("inclusion", 2), meta=graph().meta.model_copy(update={"nct_id": "NCT00000003", "condition": "Melanoma"}))
    studies = peer_studies(30)
    for s in studies[:3]:
        s["protocolSection"]["conditionsModule"] = {"conditions": ["Melanoma"]}
    studies[0]["protocolSection"]["armsInterventionsModule"]["interventions"] = [{"name": "Nivolumab", "type": "BIOLOGICAL"}]
    t = pr.build_table(g, ps, studies, TODAY)
    assert len(t.rows) == 10 and "NCT00000003" not in {r.nct_id for r in t.rows}          # itself excluded
    assert t.rows[0].nct_id == "NCT00000001" and t.rows[0].similarity > t.rows[-1].similarity            # condition + drug match first
    assert [r.similarity for r in t.rows] == sorted((r.similarity for r in t.rows), reverse=True)
    assert t.this_protocol.primary_timeframe == "Week 24" and t.this_protocol.primary_endpoint == "ORR"
    assert all(r.n_visits is None for r in t.rows)                                                     # the registry has no visit schedule
    assert pr.build_table(g, ps, studies, TODAY) == t                                                  # deterministic


def test_key_eligibility_reads_inclusion_ecog_only():
    text = "Inclusion Criteria:\n* ECOG 0 or 1\nExclusion Criteria:\n* ECOG 3 or 4\n"
    assert pr.key_eligibility(text, 18, None) == ["Age 18+", "ECOG 0-1"]
    assert pr.key_eligibility("", None, 75) == ["Age up to 75"]


def test_precedent_without_peers_is_an_empty_table_not_fake_rows():
    t = pr.precedent(graph(), None)
    assert t.rows == [] and t.this_protocol.n_visits == 0
