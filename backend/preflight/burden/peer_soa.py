# ruff: noqa: E501
"""Peer schedule burden (N: peer_percentiles in CONTRACTS 4.8).

For similar trials that posted a protocol PDF we run the SAME rules-only ingest and the SAME compute_burden as for the
protocol under review, and keep a small summary per trial in data/peers/soa/{nct}.json (committed; the PDFs are not).
Peers and protocol are therefore measured identically (both are lower bounds for recurring columns), so percentiles
compare like with like even though absolute hours are assumptions.

A peer is only used if its schedule extracted plausibly (>= MIN_VISITS visits, >= MIN_PROCS procedures, >= MIN_MATCH of
procedures found in the cost table); anything else is recorded as skipped with the reason and never silently dropped.
Percentiles are computed against the peers that are both in this protocol's peer set AND summarised here; fewer than
MIN_PEERS -> None (the burden score stays neutral).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from preflight.ctgov import client

from . import burden as _burden
from .models import BurdenReport, PeerPercentiles, PeerQuery
from .peers import LIMIT, percentile

log = logging.getLogger(__name__)
DIR = Path(__file__).resolve().parents[3] / "data" / "peers" / "soa"
PDF_DIR = Path(__file__).resolve().parents[3] / "data" / "peers" / "protocols"
MIN_VISITS, MIN_PROCS, MIN_MATCH, MIN_PEERS = 3, 5, 0.6, 8


def summary(nct: str, graph) -> dict:
    """The record kept for one peer: the burden totals, or why the schedule was not usable."""
    soa = graph.soa
    if soa is None or len(soa.visits) < MIN_VISITS or len(soa.procedures) < MIN_PROCS:
        return {"nct_id": nct, "usable": False, "reason": "no extractable schedule" if soa is None or not soa.visits else "schedule too small to trust"}
    rep = _burden.compute(graph)
    share = rep.coverage.matched / rep.coverage.procedures if rep.coverage and rep.coverage.procedures else 0.0
    if share < MIN_MATCH:
        return {"nct_id": nct, "usable": False, "reason": f"only {share:.0%} of procedures found in the cost table"}
    p = rep.per_patient
    return {"nct_id": nct, "usable": True, "patient_hours": p.patient_hours, "procedures_total": p.procedures_total, "visits": p.visits,
            "match_share": round(share, 2), "version": rep.assumptions.version}


def load(nct: str) -> dict | None:
    path = DIR / f"{nct}.json"
    return json.loads(path.read_text()) if path.exists() else None


def save(rec: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{rec['nct_id']}.json").write_text(json.dumps(rec, indent=1, sort_keys=True))


async def build(query: PeerQuery, n_target: int = 30, exclude: set[str] = frozenset()) -> list[dict]:
    """Download peers' protocols (those with a posted PDF), summarise their schedules, save, stop at n_target usable."""
    from preflight.pipeline import ingest_file

    cands = await client.search_peers(query.condition, query.phase, query.start_year_min, LIMIT, fields="NCTId", protocol_only=True)
    ncts = [c["protocolSection"]["identificationModule"]["nctId"] for c in cands]
    out = []
    for nct in (n for n in ncts if n not in exclude):
        rec = load(nct)
        if rec is None:
            try:
                pdf = await client.download_protocol(nct, str(PDF_DIR))
                if pdf is None:
                    rec = {"nct_id": nct, "usable": False, "reason": "no protocol document"}
                else:
                    graph = await ingest_file(pdf, nct_id=nct, use_llm=False)
                    rec = summary(nct, graph)
            except Exception as e:  # one bad PDF must not stop the build; a transient failure is NOT recorded, so a rerun retries it
                log.warning("%s: %s", nct, e)
                continue
            save(rec)
        out.append(rec)
        if sum(r["usable"] for r in out) >= n_target:
            break
    return out


def percentiles(report: BurdenReport, peer_ncts: set[str]) -> PeerPercentiles | None:
    """This protocol's burden against summarised peers that are in its peer set, or None when too few."""
    recs = [r for n in sorted(peer_ncts) if (r := load(n)) and r.get("usable")]
    if len(recs) < MIN_PEERS or report.per_patient.visits == 0:
        return None
    p = report.per_patient
    pct = {k: percentile(float(v), [float(r[k]) for r in recs]) for k, v in
           (("patient_hours", p.patient_hours), ("procedures_total", p.procedures_total), ("visits", p.visits))}
    return PeerPercentiles(**pct, n_peers_with_soa=len(recs))


if __name__ == "__main__":
    import argparse
    import asyncio

    ap = argparse.ArgumentParser(description="Summarise peers' schedules: python -m preflight.burden.peer_soa 'Melanoma' PHASE2 [-n 30]")
    ap.add_argument("condition")
    ap.add_argument("phase", nargs="?")
    ap.add_argument("-n", type=int, default=30)
    a = ap.parse_args()
    got = asyncio.run(build(PeerQuery(condition=a.condition, phase=a.phase, start_year_min=2015), a.n))
    print(f"{sum(r['usable'] for r in got)} usable of {len(got)} tried")
    for r in got:
        print(r["nct_id"], "usable" if r["usable"] else f"skipped: {r['reason']}")
