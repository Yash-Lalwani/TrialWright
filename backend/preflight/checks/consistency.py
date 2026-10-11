import re

from rapidfuzz import fuzz

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import Endpoint, ProtocolGraph, Visit

# Endpoint measure keywords -> SoA procedure keywords that collect it.
MEASURE_PROCEDURES = {
    r"\b(orr|response|pfs|progression|recist|tumou?r|dor|dcr|cbr)\b": r"tumou?r|imaging|ct|mri|scan|recist|assessment",
    r"\b(os|overall survival|survival)\b": r"survival|follow",
    r"quality of life|qol|pro\b|questionnaire|eortc|fact-|sf-36|eq-5d": r"quality|qol|pro\b|questionnaire|eortc|eq-5d",
    r"\b(pk|pharmacokinetics?|concentrations?|cmax|auc)\b": r"\bpk\b|pharmacokinetic|plasma|serum.*sample",
    r"blood pressure|\bbp\b": r"vital|blood pressure",
    r"hba1c": r"hba1c|chemistry|lab",
    r"immunogenicity|ada\b|anti-drug|antibod": r"immunogenicity|ada\b|anti-drug|antibod",
    r"biomarker|exploratory": r"biomarker|tissue|biopsy|exploratory",
}
SAFETY = re.compile(
    r"vital|ecg|electrocardio|hematology|haematology|chemistry|biochem|urinalysis|coagulation|physical|adverse|\bae\b|"
    r"pregnan|concomitant|ecog|performance status|weight|height|lab|blood test|thyroid|hepat|hbv|hcv|hiv|serology|"
    r"troponin|cardiac|echocardiogram|muga|lvef|ophthalm|safety", re.I)
ADMIN = re.compile(
    r"consent|icf|eligib|inclusion|exclusion|demograph|history|prior|randomi[sz]|registration|"
    r"dispens|administ|infusion|dosing|study drug|treatment|compliance|diary|subsequent|survival|contact", re.I)


GENERIC = {"proportion", "patients", "participants", "subjects", "percent", "percentage", "change", "baseline",
           "score", "scores", "reduction", "point", "week", "weeks", "rate", "number", "with", "from", "total", "mean",
           "time", "least", "achieving", "improvement", "days", "month", "months", "level", "levels"}


def _tokens(text: str) -> set[str]:
    """Distinctive tokens: acronyms (IGA, NRS, mTLSS) and longer non-generic words."""
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]+", text):
        low = w.lower()
        if low in GENERIC:
            continue
        if sum(c.isupper() for c in w) >= 2 or len(low) >= 5:
            out.add(low)
            out |= {part for part in low.split("-") if len(part) >= 4 and part not in GENERIC and not part.isdigit()}
    return out


def _procedures_for(endpoint: Endpoint, graph: ProtocolGraph) -> set[str]:
    measure = f"{endpoint.measure} {endpoint.text}".lower()
    wanted = _tokens(f"{endpoint.measure} {endpoint.text}")
    ids = set()
    for p in graph.soa.procedures:
        name = p.normalized_name
        if fuzz.partial_ratio(endpoint.measure.lower(), name) >= 85 or wanted & _tokens(p.name):
            ids.add(p.id)
        for m_pat, p_pat in MEASURE_PROCEDURES.items():
            if re.search(m_pat, measure) and re.search(p_pat, name):
                ids.add(p.id)
    return ids


def _cycle_length(visits: list[Visit]) -> float | None:
    days = sorted(v.study_day for v in visits if v.study_day is not None and v.study_day > 0)
    gaps = sorted(b - a for a, b in zip(days, days[1:], strict=False) if b > a)
    return gaps[len(gaps) // 2] if gaps else None


def _recurring(day: float, v: Visit, cycle: float | None) -> bool:
    """'Cycles 7-17 Day 1' or 'Cycle 18 and beyond': repeats every cycle from its first day."""
    if v.study_day is None or not cycle:
        return False
    m = re.search(r"cycles?\s*(\d+)\s*(?:-\s*(\d+)|and beyond|onward|\+)", v.name, re.I)
    if not m:
        return False
    end = v.study_day + (int(m.group(2)) - int(m.group(1))) * cycle if m.group(2) else float("inf")
    if not v.study_day <= day <= end + cycle:
        return False
    offset = (day - v.study_day) % cycle
    window = max(v.window_plus or 3, v.window_minus or 3)
    return min(offset, cycle - offset) <= window


def _visit_at(day: float, visits: list[Visit]) -> Visit | None:
    """Visit whose window covers the day (3-day tolerance when no window is given)."""
    cycle = _cycle_length(visits)
    for v in visits:
        if _recurring(day, v, cycle):
            return v
    best = None
    for v in visits:
        if v.study_day is None:
            continue
        lo = v.study_day - (v.window_minus if v.window_minus is not None else 3)
        hi = v.study_day + (v.window_plus if v.window_plus is not None else 3)
        if lo <= day <= hi and (best is None or abs(v.study_day - day) < abs(best.study_day - day)):
            best = v
    return best


def _nearest(day: float, visits: list[Visit]) -> Visit | None:
    dated = [v for v in visits if v.study_day is not None]
    return min(dated, key=lambda v: abs(v.study_day - day)) if dated else None


@check(id="C1", category="consistency", amendment_category="visit_schedule",
       standard_ref="ICH M11 1.3, 3; SPIRIT 2025 item 13", severity="major")
def endpoint_timepoint_has_visit(graph: ProtocolGraph, ctx: CheckContext):
    if not graph.soa or not graph.endpoints:
        return []
    soa_where = where(graph, graph.soa.span)
    primary = {eid for o in graph.objectives if o.level == "primary" for eid in o.endpoint_ids}
    issues = []
    for ep in graph.endpoints:
        severity = "critical" if ep.id in primary else "major"
        procs = _procedures_for(ep, graph)
        for week in ep.timepoints_weeks:
            day = week * 7 + 1
            label = f"Week {week:g}"
            visit = _visit_at(day, graph.soa.visits)
            if visit is None:
                near = _nearest(day, graph.soa.visits)
                hint = f" The nearest visit is {near.name} (Day {near.study_day:g})." if near else ""
                issues.append(issue(
                    "C1", f"{ep.measure} at {label} has no Schedule of Activities visit at that time", soa_where,
                    f"The endpoint '{ep.text}' is measured at {label} (Day {day:g}), but no SoA visit window covers "
                    f"that day.{hint} Sites will not collect the endpoint as written.",
                    fix=f"Add a {label} visit with the assessment, or move the endpoint to a scheduled visit.",
                    related=[where(graph, ep.span)], severity=severity))
            elif procs and not any(graph.soa.cells.get(visit.id, {}).get(p) for p in procs):
                names = ", ".join(p.name for p in graph.soa.procedures if p.id in procs)
                issues.append(issue(
                    "C1", f"{ep.measure} at {label} is not collected at the {visit.name} visit", soa_where,
                    f"The endpoint '{ep.text}' needs {names} at {label}, but the SoA does not mark it at "
                    f"{visit.name}.",
                    fix=f"Mark {names} at {visit.name} in the Schedule of Activities.",
                    related=[where(graph, ep.span)], severity=severity,
                    patch={"op": "set_soa_cell", "visit": visit.id, "procedure": sorted(procs)[0], "value": True}))
            elif not procs:
                issues.append(issue(
                    "C1", f"No Schedule of Activities procedure collects {ep.measure}", soa_where,
                    f"The endpoint '{ep.text}' has no matching procedure in the SoA, so it is unclear how it is "
                    f"collected at {label}.",
                    fix=f"Add the assessment for {ep.measure} to the SoA.",
                    related=[where(graph, ep.span)], severity=severity, confidence=0.8))
                break
    return issues


@check(id="C2", category="burden", amendment_category="visit_schedule",
       standard_ref="ICH M11 1.3, 8; Tufts CSDD non-core procedures", severity="minor")
def orphan_procedures(graph: ProtocolGraph, ctx: CheckContext):
    if not graph.soa or not graph.endpoints:
        return []
    served = set()
    for ep in graph.endpoints:
        served |= _procedures_for(ep, graph)
    issues = []
    for p in graph.soa.procedures:
        if p.id in served or SAFETY.search(p.name) or ADMIN.search(p.name):
            continue
        n = sum(1 for v in graph.soa.visits if graph.soa.cells.get(v.id, {}).get(p.id))
        issues.append(issue(
            "C2", f"'{p.name}' does not serve any endpoint, safety or eligibility need", where(graph, graph.soa.span),
            f"'{p.name}' is scheduled at {n} visit(s) but no objective, endpoint, safety assessment or eligibility "
            f"step uses it. Non-core procedures add patient and site burden.",
            fix=f"Link '{p.name}' to an endpoint, or remove it from the Schedule of Activities.", confidence=0.7))
    return issues


@check(id="C3", category="consistency", amendment_category="endpoints",
       standard_ref="ICH M11 3, 10; SPIRIT 2025 items 7, 12, 20", severity="major")
def objective_endpoint_analysis(graph: ProtocolGraph, ctx: CheckContext):
    issues = []
    for o in graph.objectives:
        if not o.endpoint_ids and o.level != "exploratory":
            issues.append(issue(
                "C3", f"{o.level.title()} objective has no endpoint", where(graph, o.span),
                f"The {o.level} objective '{o.text}' is not linked to any endpoint, so it cannot be evaluated.",
                fix="Add an endpoint that measures this objective.",
                severity="critical" if o.level == "primary" else "major"))
    if not graph.stats.analyses:
        return issues
    primary = {eid for o in graph.objectives if o.level == "primary" for eid in o.endpoint_ids}
    secondary = {eid for o in graph.objectives if o.level == "secondary" for eid in o.endpoint_ids}
    stats_text = " ".join(s.text for s in graph.sections if (s.m11_id or "").split(".")[0] == "10").lower()
    for ep in graph.endpoints:
        if ep.analysis_ids or ep.id not in primary | secondary:
            continue
        named = _tokens(f"{ep.measure} {ep.text}")
        if named and any(re.search(rf"\b{re.escape(t)}\b", stats_text) for t in named):
            continue  # the statistics chapter discusses this endpoint even if the LLM did not link an analysis
        safety = bool(SAFETY.search(f"{ep.measure} {ep.text}"))
        issues.append(issue(
            "C3", f"Endpoint '{ep.measure}' has no analysis method in the statistics section", where(graph, ep.span),
            f"The endpoint '{ep.text}' is not analysed in the statistical considerations section.",
            fix=f"Describe the analysis method, population and handling of missing data for {ep.measure}.",
            severity="critical" if ep.id in primary else "minor" if safety else "major"))
    return issues
