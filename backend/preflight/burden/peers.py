# ruff: noqa: E501
"""D2: compare a protocol with similar ClinicalTrials.gov trials (same condition and phase, DRUG or BIOLOGICAL,
started 2015 or later, capped at 200).

Peer values come from registry fields only, so every peer is measured the same way. This protocol's value for a metric
comes from the extracted graph; a metric is reported only when that value exists and there are enough peers, so
nothing is invented. Registry criteria are counted from the registry's own bullets; the protocol's from extracted
criteria. The two can split compound criteria differently, so treat criteria counts as approximate.
"""
from __future__ import annotations

import asyncio
import logging
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from preflight.ctgov import client

from ._graph_compat import ProtocolGraph
from .models import PeerMetric, PeerQuery, PeerSet, PeerTrial

log = logging.getLogger(__name__)
MIN_PEERS = 8            # fewer than this: no peer comparison at all
GOOD_PEERS = 50          # spec: 50 to 200 peers; the search broadens the condition until it reaches this
START_YEAR_MIN = 2015
LIMIT = 200

LABELS = {
    "n_inclusion_criteria": "Inclusion criteria", "n_exclusion_criteria": "Exclusion criteria",
    "n_primary_outcomes": "Primary outcomes", "n_secondary_outcomes": "Secondary outcomes",
    "enrollment": "Enrollment", "n_arms": "Arms", "min_age": "Minimum age (years)", "max_age": "Maximum age (years)",
    "duration_months": "Start to primary completion (months)",
}
BULLET = re.compile(r"^\s*(?:[*•\-–]|\d+[.)])\s+\S")


def parse_criteria(text: str | None) -> tuple[int | None, int | None]:
    """(inclusion count, exclusion count) from the registry's 'Inclusion Criteria: ... Exclusion Criteria: ...' text.
    A criterion is a bullet or numbered line; if a section has none, its non-empty lines are counted."""
    if not text:
        return None, None
    parts = re.split(r"(?im)^\s*exclusion criteria:?\s*$", text, maxsplit=1)
    inc_text = re.sub(r"(?im)^\s*inclusion criteria:?\s*$", "", parts[0])
    exc_text = parts[1] if len(parts) > 1 else ""

    def count(block: str) -> int | None:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            return None
        bullets = sum(bool(BULLET.match(ln)) for ln in lines)
        return bullets or len(lines)

    return count(inc_text), count(exc_text)


def years(text: str | None) -> float | None:
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(year|month|week|day)", text or "", re.I)
    return None if not m else float(m.group(1)) * {"year": 1, "month": 1 / 12, "week": 1 / 52, "day": 1 / 365}[m.group(2).lower()]


def _month(s: str | None) -> date | None:
    m = re.match(r"(\d{4})-(\d{2})", s or "")
    return date(int(m.group(1)), int(m.group(2)), 1) if m else None


def peer_values(study: dict) -> dict[str, float | None]:
    ps = study.get("protocolSection", {})
    inc, exc = parse_criteria(ps.get("eligibilityModule", {}).get("eligibilityCriteria"))
    start = _month(ps.get("statusModule", {}).get("startDateStruct", {}).get("date"))
    end = _month(ps.get("statusModule", {}).get("primaryCompletionDateStruct", {}).get("date"))
    out = ps.get("outcomesModule", {})
    elig = ps.get("eligibilityModule", {})
    return {
        "n_inclusion_criteria": inc, "n_exclusion_criteria": exc,
        "n_primary_outcomes": len(out["primaryOutcomes"]) if out.get("primaryOutcomes") else None,
        "n_secondary_outcomes": len(out.get("secondaryOutcomes") or []) if out.get("primaryOutcomes") else None,
        "enrollment": ps.get("designModule", {}).get("enrollmentInfo", {}).get("count"),
        "n_arms": len(ps.get("armsInterventionsModule", {}).get("armGroups") or []) or None,
        "min_age": years(elig.get("minimumAge")), "max_age": years(elig.get("maximumAge")),
        "duration_months": round((end.year - start.year) * 12 + end.month - start.month) if start and end and end >= start else None,
    }


def protocol_values(graph: ProtocolGraph) -> dict[str, float | None]:
    """This protocol's value per metric, or None when the extraction did not produce one."""
    prim = {e for o in graph.objectives if o.level == "primary" for e in o.endpoint_ids}
    sec = {e for o in graph.objectives if o.level == "secondary" for e in o.endpoint_ids}
    n_inc = sum(c.kind == "inclusion" for c in graph.criteria)
    n_exc = sum(c.kind == "exclusion" for c in graph.criteria)
    sizes = [float(n.value) for n in graph.numbers if n.kind == "sample_size"]
    return {
        "n_inclusion_criteria": n_inc or None, "n_exclusion_criteria": n_exc or None,
        "n_primary_outcomes": len(prim) or None, "n_secondary_outcomes": len(sec) or None,
        "enrollment": graph.stats.sample_size or (max(set(sizes), key=sizes.count) if sizes else None),
        "n_arms": graph.meta.n_arms, "min_age": graph.min_age, "max_age": graph.max_age, "duration_months": None,
    }


def percentile(value: float, peers: list[float]) -> float:
    """Mid-rank percentile: ties count half, so a value equal to every peer is the 50th percentile."""
    below = sum(p < value for p in peers)
    equal = sum(p == value for p in peers)
    return round(100 * (below + 0.5 * equal) / len(peers), 1)


def build_peer_set(values: dict[str, float | None], studies: list[dict], query: PeerQuery, own_nct: str | None = None) -> PeerSet | None:
    """Pure function: protocol values + peer registry records -> PeerSet (None if too few peers)."""
    studies = [s for s in studies if s.get("protocolSection", {}).get("identificationModule", {}).get("nctId") != own_nct]
    if len(studies) < MIN_PEERS:
        return None
    rows = [peer_values(s) for s in studies]
    metrics = []
    for key, label in LABELS.items():
        v = values.get(key)
        dist = sorted(float(r[key]) for r in rows if r[key] is not None)
        if v is None or len(dist) < MIN_PEERS:
            continue
        q = statistics.quantiles(dist, n=4, method="inclusive")
        metrics.append(PeerMetric(metric=key, label=label, value=float(v), percentile=percentile(float(v), dist),
                                  peer_median=statistics.median(dist), peer_p25=q[0], peer_p75=q[2], distribution=dist))
    trials = []
    for s in studies:
        ps = s["protocolSection"]
        trials.append(PeerTrial(
            nct_id=ps["identificationModule"]["nctId"], title=ps["identificationModule"].get("briefTitle", ""),
            sponsor=ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
            phase="/".join(ps.get("designModule", {}).get("phases", [])),
            enrollment=ps.get("designModule", {}).get("enrollmentInfo", {}).get("count"),
            start_date=ps.get("statusModule", {}).get("startDateStruct", {}).get("date")))
    return PeerSet(query=query, n=len(studies), metrics=metrics, hotspot_issue_ids=[], trials=trials)


def _run(coro):
    """Run a coroutine from sync code, also when called inside a running event loop (the pipeline uses to_thread)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(asyncio.run, coro).result()


def normalise_phase(phase: str | None) -> str | None:
    m = re.search(r"([123])", phase or "")
    return f"PHASE{m.group(1)}" if m else None


def broaden(condition: str) -> list[str]:
    """The condition, then versions with leading words dropped: 'Moderate to Severe Atopic Hand and Foot Dermatitis' ->
    '... Hand and Foot Dermatitis' -> ... -> 'Dermatitis'. Registry conditions are often far more specific than the
    index, so the exact string can match one trial while its head noun matches hundreds."""
    words = re.sub(r"[,/()]+", " ", condition).split()
    out = [condition]
    for i in range(1, len(words)):
        cand = " ".join(words[i:])
        if len(cand) > 3 and cand not in out:
            out.append(cand)
    return out


async def _condition_candidates(graph: ProtocolGraph) -> list[str]:
    registry: list[str] = []
    if graph.meta.nct_id:
        try:
            rec = await client.get_study(graph.meta.nct_id)
            registry = rec.get("protocolSection", {}).get("conditionsModule", {}).get("conditions") or []
        except Exception as e:  # offline and not cached
            log.info("registry condition unavailable: %s", e)
    seed = registry[:1] or ([graph.meta.condition] if graph.meta.condition else [])
    cands: list[str] = [*registry, *(c for s in seed for c in broaden(s)), *([graph.meta.condition] if graph.meta.condition else [])]
    return list(dict.fromkeys(c for c in cands if c))


async def _find(graph: ProtocolGraph) -> PeerSet | None:
    phase = normalise_phase(graph.meta.phase)
    best: tuple[int, str] | None = None
    chosen = None
    for cond in await _condition_candidates(graph):
        n = len(await client.search_peers(cond, phase, START_YEAR_MIN, LIMIT, fields="NCTId"))
        if n >= GOOD_PEERS:
            chosen = cond
            break
        if n >= MIN_PEERS and (best is None or n > best[0]):
            best = (n, cond)
    chosen = chosen or (best[1] if best else None)
    if chosen is None:
        return None
    studies = await client.search_peers(chosen, phase, START_YEAR_MIN, LIMIT, fields=client.PEER_FIELDS)
    query = PeerQuery(condition=chosen, phase=phase, start_year_min=START_YEAR_MIN)   # the query actually used
    return build_peer_set(protocol_values(graph), studies, query, graph.meta.nct_id)


def find(graph: ProtocolGraph) -> PeerSet | None:
    """Peers for a protocol, or None (no condition, too few peers, offline). Never raises: a run must not fail on this."""
    try:
        return _run(_find(graph))
    except Exception as e:
        log.warning("peer search failed: %s", e)
        return None


def peer_studies(query: PeerQuery, fields: str | None = None) -> list[dict]:
    """The registry records behind a PeerSet (disk-cached, so no network after find_peers). [] on any failure."""
    if not query.condition:
        return []
    try:
        return _run(client.search_peers(query.condition, query.phase, query.start_year_min, LIMIT, fields=fields or client.PEER_FIELDS))
    except Exception as e:
        log.warning("peer records unavailable: %s", e)
        return []
