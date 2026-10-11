# ruff: noqa: E501
"""Amendment-risk sub-score: how far the protocol's eligibility and endpoint complexity sits above similar registered trials.

Metrics: inclusion criteria, exclusion criteria, primary outcomes, secondary outcomes (peer percentiles from find_peers). Burden
metrics are left out on purpose: they already feed the Burden sub-score, and counting them twice would double their weight.

Per metric, risk is 0 up to the peer upper quartile (75th percentile) and rises linearly to 100 at the 100th percentile. The
score is 100 minus the mean risk. A protocol at or below the upper quartile on every metric scores 100; one at the 95th
percentile on all four scores 20. With fewer than MIN_METRICS metrics (no peers, or nothing extracted) the score is None,
meaning NOT ASSESSED; a missing comparison must not read as 'no risk'.

This measures complexity relative to peers. It is not a calibrated probability of amendment. The only outcome evidence we
have is exploratory (data/bench/case_studies.json: inclusion-count outliers were relaxed later more often).
"""
from __future__ import annotations

from .models import PeerSet

METRICS = ("n_inclusion_criteria", "n_exclusion_criteria", "n_primary_outcomes", "n_secondary_outcomes")
START = 75.0      # percentile where risk begins
MIN_METRICS = 2


def risk_from_percentile(percentile: float) -> float:
    return max(0.0, min(100.0, (percentile - START) / (100.0 - START) * 100.0))


def amendment_risk_score(peers: PeerSet | None) -> float | None:
    if peers is None:
        return None
    pcts = [m.percentile for m in peers.metrics if m.metric in METRICS]
    if len(pcts) < MIN_METRICS:
        return None
    return round(100.0 - sum(risk_from_percentile(p) for p in pcts) / len(pcts), 1)
