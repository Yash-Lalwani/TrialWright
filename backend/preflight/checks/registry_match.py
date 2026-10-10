# ruff: noqa: E501
"""C10: protocol vs ClinicalTrials.gov record (minimum age, enrollment, primary outcome timeframe).

The registry may have been updated after the protocol version under review, so every message says which record it
compared with. Enrollment is only compared when the registry value is an ESTIMATE (an ACTUAL count is what happened,
not what the protocol planned).
"""
from __future__ import annotations

import re

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import ProtocolGraph

UNIT_WEEKS = {"day": 1 / 7, "week": 1.0, "month": 52 / 12, "year": 52.0}


def years(text: str | None) -> float | None:
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(year|month|week|day)s?", text or "", re.I)
    return float(m.group(1)) * UNIT_WEEKS[m.group(2).lower()] / 52 if m else None


def timeframe_weeks(text: str | None) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(day|week|month|year)s?", text or "", re.I)
    return float(m.group(1)) * UNIT_WEEKS[m.group(2).lower()] if m else None


def _src(record: dict) -> str:
    upd = record.get("protocolSection", {}).get("statusModule", {}).get("lastUpdatePostDateStruct", {}).get("date")
    nct = record.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "the registry record")
    return f"{nct}" + (f" (last updated {upd})" if upd else "")


@check(id="C10", category="consistency", amendment_category="registry",
       standard_ref="ICH M11 1.1; ClinicalTrials.gov data element definitions", severity="major")
def matches_registry(graph: ProtocolGraph, ctx: CheckContext):
    rec = ctx.registry_record
    if not rec:
        return []
    ps = rec.get("protocolSection", {})
    ref, out = _src(rec), []

    reg_min = years(ps.get("eligibilityModule", {}).get("minimumAge"))
    if reg_min is not None and graph.min_age is not None and abs(reg_min - graph.min_age) > 0.5:
        fact = next((n for n in graph.numbers if n.kind == "age_min" and float(n.value) == graph.min_age), None)
        out.append(issue("C10", f"Minimum age {graph.min_age:g} differs from the registry record ({reg_min:g})",
                         where(graph, fact.span if fact else None),
                         f"The protocol requires age at least {graph.min_age:g} years but {ref} lists {reg_min:g}.",
                         fix="Update the protocol or the registry entry so both state the same minimum age."))

    enr = ps.get("designModule", {}).get("enrollmentInfo", {})
    if enr.get("type") == "ESTIMATED" and enr.get("count") and graph.stats.sample_size \
            and int(enr["count"]) != int(graph.stats.sample_size):
        fact = next((n for n in graph.numbers if n.kind == "sample_size" and float(n.value) == graph.stats.sample_size), None)
        out.append(issue("C10", f"Enrollment {graph.stats.sample_size} differs from the registry record ({enr['count']})",
                         where(graph, fact.span if fact else None),
                         f"The protocol plans {graph.stats.sample_size} participants but {ref} estimates {enr['count']}.",
                         fix="Align the protocol and the registry enrollment."))

    primary = [e for e in graph.endpoints if any(o.endpoint_ids and e.id in o.endpoint_ids and o.level == "primary"
                                                 for o in graph.objectives)]
    reg_tf = [w for o in ps.get("outcomesModule", {}).get("primaryOutcomes", []) if (w := timeframe_weeks(o.get("timeFrame")))]
    proto_tp = {t for e in primary for t in e.timepoints_weeks}
    if reg_tf and proto_tp and not any(abs(w - t) <= 1.0 for w in reg_tf for t in proto_tp):
        e = primary[0]
        out.append(issue("C10", "Primary endpoint timepoint differs from the registry record", where(graph, e.span),
                         f"The protocol measures the primary endpoint at week(s) {sorted(proto_tp)} but {ref} gives "
                         f"{sorted(round(w, 1) for w in reg_tf)} week(s).",
                         fix="Align the primary outcome timeframe in the protocol and the registry.", severity="minor"))
    return out
