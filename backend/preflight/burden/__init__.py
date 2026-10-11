# ruff: noqa: E501
"""Burden, peers, hotspots, precedent (D1 to D3, E6). Interface per CONTRACTS.md 3.4.

All of D1 (compute_burden, burden_score), D2 (find_peers), D3 (hotspots) and E6 (precedent) are REAL.
Set PREFLIGHT_BURDEN_STUBS=1 to get the CONTRACTS.md example data instead (for frontend demos and contract tests).
Without it nothing invented is ever shown: no peers -> no hotspots, an empty precedent table, burden score 50.
"""
from __future__ import annotations

import os

from ._graph_compat import Issue, ProtocolGraph
from .models import BurdenReport, PeerSet, PrecedentTable
from . import _examples, peers as _peers
from . import burden as _burden, hotspots as _hotspots, peer_soa as _peer_soa, precedent as _precedent

STUB = False
NEUTRAL_BURDEN = 50.0


def _examples_on() -> bool:
    return os.environ.get("PREFLIGHT_BURDEN_STUBS") == "1"


def find_peers(graph: ProtocolGraph) -> PeerSet | None:
    """REAL (D2): similar ClinicalTrials.gov trials with percentiles, or None when none can be found."""
    return PeerSet.model_validate(_examples.PEERS) if _examples_on() else _peers.find(graph)


def compute_burden(graph: ProtocolGraph, peers: PeerSet | None) -> BurdenReport:
    """REAL (D1). peer_percentiles come from peers whose posted protocols we summarised (peer_soa); None when fewer than 8."""
    if _examples_on():
        return BurdenReport.model_validate(_examples.BURDEN)
    report = _burden.compute(graph)
    ncts = {t.nct_id for t in peers.trials} if peers is not None else set()
    return report.model_copy(update={"peer_percentiles": _peer_soa.percentiles(report, ncts, graph.meta.nct_id)})


def hotspots(graph: ProtocolGraph, peers: PeerSet | None) -> list[Issue]:
    """REAL (D3): amendment-risk issues (category "amendment_risk"): where the protocol is an outlier among peers."""
    if _examples_on():
        return [Issue.model_validate(i) for i in _examples.HOTSPOT_ISSUES] if peers is not None else []
    return _hotspots.hotspots(graph, peers)


def precedent(graph: ProtocolGraph, peers: PeerSet | None) -> PrecedentTable:
    """REAL (E6): top 10 most similar registered trials and what they chose."""
    return PrecedentTable.model_validate(_examples.PRECEDENT) if _examples_on() else _precedent.precedent(graph, peers)


def burden_score(report: BurdenReport) -> float:
    """0-100 (higher = lighter burden). STUB: neutral 50, or the CONTRACTS.md example 58 when examples are on."""
    return 58.0 if _examples_on() else _burden.score(report)


__all__ = ["find_peers", "compute_burden", "hotspots", "precedent", "burden_score", "STUB"]
