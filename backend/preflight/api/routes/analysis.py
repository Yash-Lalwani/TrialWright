"""CONTRACTS 4.8 burden, 4.9 peers, 4.10 precedent. B owns this file; A's main.py mounts it automatically.

Each endpoint rebuilds its answer from the protocol graph stored by the run. Peer lookups are disk-cached
(data/peers/api), so repeat calls do not touch the network. The blocking work runs in FastAPI's thread pool (plain def).
"""
from fastapi import APIRouter, HTTPException
from sqlmodel import select

from preflight import burden
from preflight.api import service
from preflight.db import IssueRow, Protocol, Run, session
from preflight.graph.models import ProtocolGraph

router = APIRouter(prefix="/api")


def _graph(s, run_id: str) -> tuple[ProtocolGraph, Run]:
    run = service.get_or_404(s, Run, run_id, "Run")
    protocol = s.get(Protocol, run.protocol_id)
    if protocol is None or not protocol.graph:
        raise HTTPException(409, f"Run {run_id} has no protocol graph yet (status: {run.status})")
    return ProtocolGraph.model_validate(protocol.graph), run


@router.get("/runs/{run_id}/burden")
def get_burden(run_id: str):
    with session() as s:
        graph, _ = _graph(s, run_id)
    return burden.compute_burden(graph, burden.find_peers(graph)).model_dump()


@router.get("/runs/{run_id}/peers")
def get_peers(run_id: str):
    with session() as s:
        graph, run = _graph(s, run_id)
        rows = s.exec(select(IssueRow).where(IssueRow.run_id == run.id)).all()
        hotspot_ids = [r.id for r in rows if r.data.get("check_id") == "D3"]
    peers = burden.find_peers(graph)
    if peers is None:
        raise HTTPException(404, "No peer set: the condition is unknown or too few similar trials were found")
    return peers.model_copy(update={"hotspot_issue_ids": sorted(hotspot_ids)}).model_dump()


@router.get("/runs/{run_id}/precedent")
def get_precedent(run_id: str):
    with session() as s:
        graph, _ = _graph(s, run_id)
    return burden.precedent(graph, burden.find_peers(graph)).model_dump()
