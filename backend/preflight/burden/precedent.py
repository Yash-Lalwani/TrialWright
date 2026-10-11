# ruff: noqa: E501
"""E6: precedent table. The most similar registered trials and what they chose for the primary endpoint, timeframe,
eligibility, enrollment and visit count.

Similarity (0 to 1) is a fixed weighted sum, not a model: condition words 0.35, phase 0.15, intervention words 0.25,
enrollment closeness 0.15, recency 0.10. n_visits is None for peers: the registry does not record visit schedules
(peer schedules need protocol PDFs; see burden peer percentiles).
"""
from __future__ import annotations

import math
import re
from datetime import date

from preflight.ctgov import client
from preflight.graph.models import ProtocolGraph

from . import peers as _peers
from .models import PeerSet, PrecedentRow, PrecedentTable, ThisProtocol

FIELDS = client.PEER_FIELDS + ",PrimaryOutcomeTimeFrame,InterventionName,InterventionType"
TOP = 10
W = {"condition": 0.35, "phase": 0.15, "intervention": 0.25, "enrollment": 0.15, "recency": 0.10}
STOP = {"the", "and", "of", "in", "with", "for", "a", "an", "to", "or", "mg", "placebo", "plus", "versus", "vs", "study", "treatment", "drug"}
ECOG = re.compile(r"(?:ECOG|performance status)[^.;\n]{0,60}?\b([0-5])\s*(?:(?:-|–|to|or)\s*([0-5]))?", re.I)
TIMEFRAME = re.compile(r"((?:up to |through |at |by )?(?:week|month|day|year)s?\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?[\s-]*(?:week|month|day|year)s?)", re.I)


def words(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", (text or "").lower()) if w not in STOP}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def key_eligibility(criteria_text: str, min_age: float | None, max_age: float | None) -> list[str]:
    """Short comparable facts: age range and ECOG range, from the same regex on both sides."""
    out = []
    if min_age is not None or max_age is not None:
        lo = f"{min_age:g}" if min_age is not None else ""
        hi = f"{max_age:g}" if max_age is not None else ""
        out.append(f"Age {lo}+" if lo and not hi else f"Age {lo}-{hi}" if lo else f"Age up to {hi}")
    inclusion = re.split(r"(?im)^\s*exclusion criteria:?\s*$", criteria_text or "", maxsplit=1)[0]
    m = ECOG.search(inclusion)
    if m:
        out.append(f"ECOG {m.group(1)}-{m.group(2)}" if m.group(2) else f"ECOG {m.group(1)}")
    return out


def _age_years(text: str | None) -> float | None:
    return _peers.years(text)


def this_protocol(graph: ProtocolGraph) -> ThisProtocol:
    prim = next((o for o in graph.objectives if o.level == "primary"), None)
    ep = next((e for e in graph.endpoints if prim and e.id in prim.endpoint_ids), None) or (graph.endpoints[0] if graph.endpoints else None)
    endpoint = (ep.measure or ep.text) if ep else (prim.text if prim else "")
    timeframe = ""
    if ep and ep.timepoints_weeks:
        timeframe = f"Week {ep.timepoints_weeks[0]:g}"
    elif ep and (m := TIMEFRAME.search(ep.text)):
        timeframe = m.group(1).strip()
    text = " ".join(c.text for c in graph.criteria if c.kind == "inclusion")
    sizes = [float(n.value) for n in graph.numbers if n.kind == "sample_size"]
    enrollment = graph.stats.sample_size or (int(max(set(sizes), key=sizes.count)) if sizes else None)
    return ThisProtocol(primary_endpoint=endpoint[:200], primary_timeframe=timeframe, key_eligibility=key_eligibility(text, graph.min_age, graph.max_age),
                        enrollment=enrollment, n_visits=len(graph.soa.visits) if graph.soa else 0)


def similarity(graph: ProtocolGraph, peers: PeerSet, study: dict, today: date | None = None) -> float:
    ps = study.get("protocolSection", {})
    cond = jaccard(words(graph.meta.condition or peers.query.condition), words(" ".join(ps.get("conditionsModule", {}).get("conditions", []))))
    phase = 1.0 if peers.query.phase and peers.query.phase in ps.get("designModule", {}).get("phases", []) else 0.0
    arms = words(" ".join(a.name for a in graph.arms))
    names = words(" ".join(i.get("name", "") for i in ps.get("armsInterventionsModule", {}).get("interventions", [])))
    inter = jaccard(arms, names)
    enr_peer = ps.get("designModule", {}).get("enrollmentInfo", {}).get("count")
    own = this_protocol(graph).enrollment
    enr = max(0.0, 1 - abs(math.log10(enr_peer / own)) / 1.0) if enr_peer and own else 0.0
    m = re.match(r"(\d{4})", ps.get("statusModule", {}).get("startDateStruct", {}).get("date") or "")
    year = (today or date.today()).year
    rec = max(0.0, 1 - (year - int(m.group(1))) / 12) if m else 0.0
    return round(W["condition"] * cond + W["phase"] * phase + W["intervention"] * inter + W["enrollment"] * enr + W["recency"] * rec, 3)


def _row(study: dict, sim: float) -> PrecedentRow:
    ps = study["protocolSection"]
    prim = (ps.get("outcomesModule", {}).get("primaryOutcomes") or [{}])[0]
    elig = ps.get("eligibilityModule", {})
    return PrecedentRow(
        nct_id=ps["identificationModule"]["nctId"], title=ps["identificationModule"].get("briefTitle", ""),
        sponsor=ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
        phase="/".join(ps.get("designModule", {}).get("phases", [])), similarity=sim,
        primary_endpoint=prim.get("measure", ""), primary_timeframe=prim.get("timeFrame", ""),
        key_eligibility=key_eligibility(elig.get("eligibilityCriteria", ""), _age_years(elig.get("minimumAge")), _age_years(elig.get("maximumAge"))),
        enrollment=ps.get("designModule", {}).get("enrollmentInfo", {}).get("count"), n_visits=None)


def build_table(graph: ProtocolGraph, peers: PeerSet, studies: list[dict], today: date | None = None) -> PrecedentTable:
    """Pure function: the top TOP peers by similarity (ties by NCT id), never this protocol itself."""
    own = graph.meta.nct_id
    scored = sorted(((similarity(graph, peers, s, today), s["protocolSection"]["identificationModule"]["nctId"], s) for s in studies
                     if s.get("protocolSection", {}).get("identificationModule", {}).get("nctId") != own), key=lambda t: (-t[0], t[1]))
    return PrecedentTable(this_protocol=this_protocol(graph), rows=[_row(s, sim) for sim, _, s in scored[:TOP]])


def precedent(graph: ProtocolGraph, peers: PeerSet | None) -> PrecedentTable:
    if peers is None:
        return PrecedentTable(this_protocol=this_protocol(graph), rows=[])
    return build_table(graph, peers, _peers.peer_studies(peers.query, FIELDS))
