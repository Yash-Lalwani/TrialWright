from preflight.burden.models import PeerMetric, PeerQuery, PeerSet
from preflight.burden.risk import amendment_risk_score, risk_from_percentile


def peers_with(**pcts):
    metrics = [PeerMetric(metric=k, label=k, value=1.0, percentile=v, peer_median=1.0, peer_p25=1.0, peer_p75=1.0,
                          distribution=[1.0]) for k, v in pcts.items()]
    return PeerSet(query=PeerQuery(condition="x", phase="PHASE2", start_year_min=2015), n=50, metrics=metrics,
                   hotspot_issue_ids=[], trials=[])


def test_risk_starts_at_the_upper_quartile_and_reaches_100_at_the_top():
    assert [risk_from_percentile(p) for p in (0, 50, 75, 87.5, 100)] == [0.0, 0.0, 0.0, 50.0, 100.0]


def test_typical_protocols_score_100_and_heavy_ones_score_low():
    assert amendment_risk_score(peers_with(n_inclusion_criteria=40, n_exclusion_criteria=60)) == 100.0
    assert amendment_risk_score(peers_with(n_inclusion_criteria=95, n_exclusion_criteria=95,
                                           n_primary_outcomes=95, n_secondary_outcomes=95)) == 20.0
    assert amendment_risk_score(peers_with(n_inclusion_criteria=50, n_exclusion_criteria=85.4,
                                           n_primary_outcomes=29, n_secondary_outcomes=72.2)) == 89.6


def test_without_peers_or_enough_metrics_it_is_not_assessed_not_100():
    assert amendment_risk_score(None) is None
    assert amendment_risk_score(peers_with(n_exclusion_criteria=99)) is None            # one metric is not enough
    assert amendment_risk_score(peers_with(enrollment=99, min_age=99)) is None          # not amendment-risk metrics
