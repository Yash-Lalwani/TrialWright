"""Burden, peers, hotspots, precedent (D1 to D3, E6). Interface per CONTRACTS.md 3.4.

H2 STUBS. By default they are INERT so real runs never show invented findings:
find_peers -> None (so the pipeline skips hotspots), burden_score -> 50 (A's neutral value).
Set PREFLIGHT_BURDEN_STUBS=1 to get the CONTRACTS.md example data (for frontend demos and contract tests).
Real implementations land H7 to H15 (compute_burden H7-11; peers, hotspots, precedent H11-15).
"""
from __future__ import annotations

import os

from ._graph_compat import Issue, ProtocolGraph
from .models import BurdenReport, PeerSet, PrecedentTable
from . import _examples

STUB = True
NEUTRAL_BURDEN = 50.0


def _examples_on() -> bool:
    return os.environ.get("PREFLIGHT_BURDEN_STUBS") == "1"


def find_peers(graph: ProtocolGraph) -> PeerSet | None:
    return PeerSet.model_validate(_examples.PEERS) if _examples_on() else None


def compute_burden(graph: ProtocolGraph, peers: PeerSet | None) -> BurdenReport:
    return BurdenReport.model_validate(_examples.BURDEN)


def hotspots(graph: ProtocolGraph, peers: PeerSet | None) -> list[Issue]:
    """Amendment-risk issues (category "amendment_risk")."""
    if not _examples_on() or peers is None:
        return []
    return [Issue.model_validate(i) for i in _examples.HOTSPOT_ISSUES]


def precedent(graph: ProtocolGraph, peers: PeerSet | None) -> PrecedentTable:
    return PrecedentTable.model_validate(_examples.PRECEDENT)


def burden_score(report: BurdenReport) -> float:
    """0-100 (higher = lighter burden). STUB: neutral 50, or the CONTRACTS.md example 58 when examples are on."""
    return 58.0 if _examples_on() else NEUTRAL_BURDEN


__all__ = ["find_peers", "compute_burden", "hotspots", "precedent", "burden_score", "STUB"]
