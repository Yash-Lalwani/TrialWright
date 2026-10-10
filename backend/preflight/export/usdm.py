import json
from pathlib import Path

from preflight.graph.models import ProtocolGraph

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "data" / "standards" / "usdm_schema.json"
PHASES = {"PHASE1": "Phase I Trial", "PHASE2": "Phase II Trial", "PHASE3": "Phase III Trial",
          "PHASE4": "Phase IV Trial"}


def _code(code: str, decode: str) -> dict:
    return {"id": f"Code_{code}", "code": code, "codeSystem": "preflight", "codeSystemVersion": "1", "decode": decode,
            "instanceType": "Code"}


def to_usdm(graph: ProtocolGraph) -> dict:
    """Map the Protocol Graph to a USDM-shaped study (field names follow USDM v3)."""
    soa = graph.soa
    encounters = [{"id": v.id, "name": v.name, "label": v.name, "instanceType": "Encounter",
                   "scheduledAtTimingId": f"Timing_{v.id}",
                   "timing": {"studyDay": v.study_day, "windowLower": v.window_minus, "windowUpper": v.window_plus}}
                  for v in (soa.visits if soa else [])]
    activities = [{"id": p.id, "name": p.name, "label": p.normalized_name, "instanceType": "Activity"}
                  for p in (soa.procedures if soa else [])]
    instances = [{"id": f"SAI_{v.id}", "encounterId": v.id, "instanceType": "ScheduledActivityInstance",
                  "activityIds": [p for p, on in soa.cells.get(v.id, {}).items() if on]}
                 for v in (soa.visits if soa else [])]
    endpoints = {e.id: e for e in graph.endpoints}
    objectives = [{"id": o.id, "name": o.id, "text": o.text, "instanceType": "Objective",
                   "level": _code(o.level.upper(), f"{o.level.title()} Objective"),
                   "endpoints": [{"id": eid, "name": eid, "text": endpoints[eid].text,
                                  "purpose": endpoints[eid].measure,
                                  "instanceType": "Endpoint",
                                  "level": _code(o.level.upper(), f"{o.level.title()} Endpoint")}
                                 for eid in o.endpoint_ids if eid in endpoints]}
                  for o in graph.objectives]
    criteria = [{"id": c.id, "name": c.id, "text": c.text, "instanceType": "EligibilityCriterion",
                 "category": _code(c.kind.upper(), f"{c.kind.title()} Criteria")} for c in graph.criteria]
    arms = [{"id": f"Arm_{i + 1}", "name": a.name, "label": a.name, "type": _code(a.type.upper(), a.type),
             "description": " ".join(x for x in (a.dose, a.route, a.frequency) if x), "instanceType": "StudyArm"}
            for i, a in enumerate(graph.arms)]
    m = graph.meta
    design = {
        "id": "StudyDesign_1", "name": "Study Design 1", "instanceType": "InterventionalStudyDesign",
        "arms": arms, "encounters": encounters, "activities": activities,
        "scheduleTimelines": [{"id": "Timeline_1", "name": "Main timeline", "mainTimeline": True,
                               "instanceType": "ScheduleTimeline", "instances": instances}],
        "objectives": objectives,
        "population": {"id": "Population_1", "name": "Trial population", "instanceType": "StudyDesignPopulation",
                       "plannedAge": {"minValue": graph.min_age, "maxValue": graph.max_age, "unit": "years"},
                       "plannedEnrollmentNumber": graph.stats.sample_size, "criteria": criteria},
        "blindingSchema": _code(m.masking or "UNKNOWN", m.masking or "Unknown"),
        "analysisPopulations": [],
    }
    version = {
        "id": "StudyVersion_1", "versionIdentifier": "1", "instanceType": "StudyVersion",
        "titles": [{"id": "Title_1", "text": m.title, "type": _code("OFFICIAL", "Official Study Title"),
                    "instanceType": "StudyTitle"}],
        "studyIdentifiers": ([{"id": "Identifier_1", "text": m.nct_id, "instanceType": "StudyIdentifier",
                               "scopeId": "ClinicalTrials.gov"}] if m.nct_id else []),
        "studyPhase": _code(m.phase, PHASES.get(m.phase, m.phase)) if m.phase else None,
        "studyDesigns": [design],
        "narrativeContentItems": [{"id": s.id, "name": s.title, "sectionNumber": s.m11_id, "text": s.text,
                                   "instanceType": "NarrativeContentItem"} for s in graph.sections if s.m11_id],
    }
    return {"usdmVersion": "3.0.0", "systemName": "Protocol Pre-Flight", "systemVersion": "0.1.0",
            "study": {"id": graph.protocol_id, "name": m.title[:120], "instanceType": "Study", "versions": [version]}}


def validate(doc: dict) -> list[str]:
    """Errors against the pinned CDISC USDM schema; an empty list when the schema is not present yet."""
    if not SCHEMA_PATH.exists():
        return []
    import jsonschema

    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in validator.iter_errors(doc)][:50]
