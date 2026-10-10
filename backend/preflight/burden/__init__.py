"""Burden, peers, hotspots, precedent (D1 to D3, E6). Interface per CONTRACTS.md 3.4.

H2 STUBS: every function returns the CONTRACTS.md example data regardless of input.
Real implementations land H7 to H15 (compute_burden H7-11; peers, hotspots, precedent H11-15).
"""
from __future__ import annotations

from ._graph_compat import Issue, ProtocolGraph
from .models import BurdenReport, PeerSet, PrecedentTable
from . import _examples

STUB = True


def find_peers(graph: ProtocolGraph) -> PeerSet:
    return PeerSet.model_validate(_examples.PEERS)


def compute_burden(graph: ProtocolGraph, peers: PeerSet | None) -> BurdenReport:
    return BurdenReport.model_validate(_examples.BURDEN)


def hotspots(graph: ProtocolGraph, peers: PeerSet) -> list[Issue]:
    """Amendment-risk issues (category "amendment_risk")."""
    return [Issue.model_validate(i) for i in _examples.HOTSPOT_ISSUES]


def precedent(graph: ProtocolGraph, peers: PeerSet) -> PrecedentTable:
    return PrecedentTable.model_validate(_examples.PRECEDENT)


def burden_score(report: BurdenReport) -> float:
    """0-100 (higher = lighter burden). STUB returns the CONTRACTS.md example sub-score."""
    return 58.0


__all__ = ["find_peers", "compute_burden", "hotspots", "precedent", "burden_score", "STUB"]
