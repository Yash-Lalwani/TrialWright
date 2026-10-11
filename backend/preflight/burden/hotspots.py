# ruff: noqa: E501
"""D3: amendment-risk hotspots. Where this protocol is an outlier among similar registered trials.

An outlier is not an error. Each finding says how the protocol compares, lists real peer trials (NCT ids) that are less
restrictive, and asks the author to confirm the choice is deliberate. We do NOT claim that outliers cause amendments;
that would need the amendment histories we do not have (see N7).

Thresholds: minor at the 85th percentile (15th for upper age), major at the 97th (3rd) with at least 30 peers, and the
value must also lie beyond the peer inter-quartile range, so ties and tiny differences never fire.
"""
from __future__ import annotations

from preflight.graph.issues import Fix, Issue, Where, Why
from preflight.graph.models import ProtocolGraph, Span

from . import peers as _peers
from .models import PeerMetric, PeerSet

MINOR, MAJOR, MAJOR_MIN_PEERS = 85.0, 97.0, 30
NCT_CITED = 3

# metric -> (direction, standard_ref, amendment_category, what it means, how to look)
RULES = {
    "n_exclusion_criteria": ("high", "ICH M11 5.3", "eligibility", "exclusion criteria", "Review each exclusion criterion for a safety or scientific rationale and drop those without one."),
    "n_inclusion_criteria": ("high", "ICH M11 5.2", "eligibility", "inclusion criteria", "Check that each inclusion criterion is needed to define the population."),
    "n_secondary_outcomes": ("high", "ICH M11 3", "endpoints", "secondary outcomes", "Confirm every secondary outcome is needed and has a planned analysis."),
    "n_primary_outcomes": ("high", "ICH M11 3", "endpoints", "primary outcomes", "State how multiplicity across primary outcomes is controlled, or reduce them."),
    "min_age": ("high", "ICH M11 5.2", "eligibility", "minimum age", "Confirm the higher minimum age is justified by the safety data or the disease."),
    "max_age": ("low", "ICH M11 5.2", "eligibility", "upper age limit", "Confirm the upper age limit is justified; most similar trials set none or a higher one."),
}
SECTIONS = {"n_exclusion_criteria": "Exclusion criteria", "n_inclusion_criteria": "Inclusion criteria", "n_secondary_outcomes": "Objectives and endpoints",
            "n_primary_outcomes": "Objectives and endpoints", "min_age": "Eligibility", "max_age": "Eligibility"}


def _span(graph: ProtocolGraph, metric: str) -> Span | None:
    if metric in ("n_exclusion_criteria", "n_inclusion_criteria"):
        kind = "exclusion" if "exclusion" in metric else "inclusion"
        return next((c.span for c in graph.criteria if c.kind == kind), None)
    if metric in ("n_primary_outcomes", "n_secondary_outcomes"):
        level = "primary" if "primary" in metric else "secondary"
        return next((o.span for o in graph.objectives if o.level == level), None)
    kind = "age_min" if metric == "min_age" else "age_max"
    return next((n.span for n in graph.numbers if n.kind == kind), None)


def _where(graph: ProtocolGraph, metric: str) -> Where:
    span = _span(graph, metric)
    if span is None:
        return Where(section=SECTIONS[metric], page=None, bbox=None, quote=None)
    hits = [s for s in graph.sections if s.page_start <= span.page <= s.page_end]
    section = max(hits, key=lambda s: (s.level, s.page_start)).title if hits else SECTIONS[metric]
    return Where(section=section, page=span.page, bbox=span.bbox, quote=span.quote)


def _fires(metric: PeerMetric, direction: str, n_peers: int) -> str | None:
    """'major', 'minor' or None."""
    high = direction == "high"
    pct = metric.percentile if high else 100 - metric.percentile
    beyond = metric.value > metric.peer_p75 if high else metric.value < metric.peer_p25
    if pct >= MAJOR and beyond and n_peers >= MAJOR_MIN_PEERS:
        return "major"
    return "minor" if pct >= MINOR and beyond else None


def _cite(metric: str, direction: str, value: float, studies: list[dict], median: float) -> list[str]:
    """Up to NCT_CITED real peer trials on the less restrictive side, the ones nearest the peer median."""
    rows = []
    for s in studies:
        v = _peers.peer_values(s).get(metric)
        if v is None:
            continue
        ok = v < value if direction == "high" else v > value
        if ok:
            rows.append((abs(v - median), s["protocolSection"]["identificationModule"]["nctId"], v))
    rows.sort()
    return [f"{nct} ({v:g})" for _, nct, v in rows[:NCT_CITED]]


def hotspots(graph: ProtocolGraph, peers: PeerSet | None) -> list[Issue]:
    if peers is None:
        return []
    studies = _peers.peer_studies(peers.query)
    issues = []
    for m in peers.metrics:
        rule = RULES.get(m.metric)
        if rule is None:
            continue
        direction, ref, amendment, noun, advice = rule
        severity = _fires(m, direction, peers.n)
        if severity is None:
            continue
        pct = m.percentile if direction == "high" else 100 - m.percentile
        if m.metric == "min_age":
            title = f"Minimum age of {m.value:g} is higher than in {pct:.0f}% of similar trials"
        elif m.metric == "max_age":
            title = f"Upper age limit of {m.value:g}: {pct:.0f}% of similar trials allow older participants"
        else:
            title = f"{m.value:g} {noun}: {pct:.0f}% of similar trials have fewer"
        cited = _cite(m.metric, direction, m.value, studies, m.peer_median)
        evidence = f" Less restrictive peers: {', '.join(cited)}." if cited else ""
        scope = f"{peers.n} registered {peers.query.phase or ''} trials in '{peers.query.condition}' (started {peers.query.start_year_min} or later)".replace("  ", " ")
        issues.append(Issue(
            id="", check_id="D3", source="rule", category="amendment_risk", severity=severity, title=title,
            where=_where(graph, m.metric), related=[],
            why=Why(explanation=(f"This protocol has {m.value:g} {noun}; the peer median is {m.peer_median:g} (middle half {m.peer_p25:g} to {m.peer_p75:g}) "
                                 f"across {scope}. An outlier is not an error, but it is a choice reviewers will ask about.{evidence}"),
                    standard_ref=ref, amendment_category=amendment),
            fix=Fix(suggestion=advice, patch=None), confidence=0.7, verified=True))
    return issues
