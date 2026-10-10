# ruff: noqa: E501
"""D1: patient and site burden from the Schedule of Activities and the cost assumptions.

Every figure derives from data/assumptions/procedure_costs.csv, which is labelled `assumption` throughout, so the
absolute numbers (hours, dollars) are order-of-magnitude. The burden SCORE uses percentiles against peers, so only
relative size matters there.

Counting rules (all deliberate, all reported):
  * each SoA column counts once. Recurring columns ("Q3W", "Cycles 7-17", "and beyond") therefore make the totals a
    LOWER bound; `coverage.recurring_columns` says how many columns are recurring;
  * in-person columns add the 'clinic visit overhead' row (travel, check-in); phone and survival follow-up do not;
  * a procedure not found in the cost table adds nothing and is listed in `coverage.unmatched`.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import costs
from ._graph_compat import ProtocolGraph
from .models import Assumptions, BurdenReport, ByVisit, Coverage, OrphanProcedure, PeerPercentiles, PerPatient

CONFIG = Path(__file__).resolve().parents[3] / "config" / "score.yaml"
DEFAULT_WEIGHTS = {"patient_hours": 0.5, "procedures_total": 0.3, "visits": 0.2}
NEUTRAL = 50.0

RECURRING = re.compile(r"\bq\s?\d+\s*[wm]\b|every\s+\d+|cycles?\s*\d+\s*(?:-|and beyond|\+)|and beyond|etc\.?|\.\.\.", re.I)
NOT_IN_PERSON = re.compile(r"phone|telephone|\bcall\b|survival follow|contact", re.I)
ORPHAN_TITLE = re.compile(r"^'(.+)' does not serve")


def visit_label(name: str) -> str:
    """'W2D1 ± 2d 2' -> 'W2D1'; 'W1D1 n/a 1 SC/IT 1' -> 'W1D1'. SoA extraction leaves window and mark text in names."""
    name = re.split(r"\s+(?:n/a\b|[±+]\s?\d)", name, maxsplit=1)[0]
    return re.sub(r"(?:\s+\d+)+$", "", name).strip() or name


def orphans(graph: ProtocolGraph) -> set[str]:
    """Procedure names A's C2 check calls orphans, so the burden page and the issue list agree.
    C2 needs LLM-extracted endpoints, so without them this is empty (not "no orphans")."""
    from preflight.checks.registry import CHECKS, CheckContext, discover

    discover()
    out = set()
    for i in CHECKS["C2"].fn(graph, CheckContext()):
        if m := ORPHAN_TITLE.match(i.title):
            out.add(m.group(1))
    return out


def compute(graph: ProtocolGraph, peer_percentiles: PeerPercentiles | None = None) -> BurdenReport:
    version, rows = costs.load()
    assumptions = Assumptions(file="data/assumptions/procedure_costs.csv", version=version)
    soa = graph.soa
    if soa is None or not soa.visits:
        return BurdenReport(per_patient=PerPatient(visits=0, procedures_total=0, invasive=0, patient_hours=0, site_hours=0,
                                                   cost_usd=0),
                            by_visit=[], orphan_procedures=[], peer_percentiles=peer_percentiles, assumptions=assumptions,
                            coverage=Coverage(procedures=0, matched=0, unmatched=[], columns=0, recurring_columns=0))
    overhead = next(r for r in rows if r.name == costs.VISIT_OVERHEAD)
    by_visit, unmatched, seen = [], set(), set()
    pat = site = cost = 0.0
    n_marks = n_invasive = recurring = 0
    occ: dict[str, list[costs.Procedure | None]] = {}
    for v in soa.visits:
        label = visit_label(v.name)
        recurring += bool(RECURRING.search(v.name))
        pm = sm = 0.0
        if not NOT_IN_PERSON.search(v.name):
            pm, sm, cost = pm + overhead.patient_minutes, sm + overhead.site_minutes, cost + overhead.cost_usd
        names = []
        for p in soa.procedures:
            if not soa.cells.get(v.id, {}).get(p.id):
                continue
            row = costs.match(p.name, rows)
            n_marks += 1
            seen.add(p.name)
            occ.setdefault(p.name, []).append(row)
            if row is None:
                unmatched.add(p.name)
                names.append(p.name)
                continue
            pm, sm, cost = pm + row.patient_minutes, sm + row.site_minutes, cost + row.cost_usd
            n_invasive += row.invasive
            names.append(row.name)
        pat, site = pat + pm, site + sm
        by_visit.append(ByVisit(visit=label, study_day=v.study_day, patient_minutes=round(pm), site_minutes=round(sm),
                                procedures=sorted(set(names))))
    orphan_names = orphans(graph)
    orphan_rows = []
    for name in sorted(orphan_names & seen):
        hits = occ[name]
        row = hits[0]
        orphan_rows.append(OrphanProcedure(name=name, occurrences=len(hits),
                                           patient_minutes=round(sum(r.patient_minutes for r in hits if r)),
                                           cost_usd=round(sum(r.cost_usd for r in hits if r))))
    return BurdenReport(
        per_patient=PerPatient(visits=len(soa.visits), procedures_total=n_marks, invasive=n_invasive,
                               patient_hours=round(pat / 60, 1), site_hours=round(site / 60, 1), cost_usd=round(cost)),
        by_visit=by_visit, orphan_procedures=orphan_rows, peer_percentiles=peer_percentiles, assumptions=assumptions,
        coverage=Coverage(procedures=len(seen), matched=len(seen) - len(unmatched), unmatched=sorted(unmatched),
                          columns=len(soa.visits), recurring_columns=recurring))


def weights() -> dict[str, float]:
    cfg = yaml.safe_load(CONFIG.read_text()) if CONFIG.exists() else {}
    return {**DEFAULT_WEIGHTS, **((cfg or {}).get("burden_percentile_weights") or {})}


def score(report: BurdenReport) -> float:
    """0-100, higher = lighter burden: 100 minus the weighted peer percentile of patient hours, procedures and visits.
    Without peer percentiles there is nothing to compare against, so the score is neutral (50), not a guess."""
    p = report.peer_percentiles
    if p is None:
        return NEUTRAL
    w = weights()
    pct = sum(w[k] * getattr(p, k) for k in w) / sum(w.values())
    return round(max(0.0, min(100.0, 100 - pct)), 1)
