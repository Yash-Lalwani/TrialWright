"""Build frontend/mocks/issues_real.json: contract-shaped issues anchored to real quotes in a real PDF."""

import re

import pymupdf

from preflight.graph.issues import Fix, Issue, Where, Why
from preflight.graph.models import Section
from preflight.ingest.pdf import read_pdf
from preflight.ingest.sections import find_sections

TEMPLATES = [
    (r"schedule of (activities|assessments)", "C1", "consistency", "critical", "visit_schedule",
     "Primary endpoint timepoint has no matching assessment in the Schedule of Activities",
     "ICH M11 1.3, 3; SPIRIT 2025 item 13", "Add the endpoint assessment to the matching SoA visit."),
    (r"objective", "C3", "consistency", "major", "endpoints",
     "Secondary objective has no endpoint with an analysis method",
     "ICH M11 3; SPIRIT 2025 item 7", "Add an endpoint and name its analysis in the statistics section."),
    (r"inclusion criteria", "C8", "consistency", "major", "eligibility",
     "Inclusion and exclusion criteria use conflicting thresholds for the same lab test",
     "ICH M11 5.1, 5.2", "Use one threshold and unit for the lab test in both lists."),
    (r"exclusion criteria", "D3", "amendment_risk", "minor", "eligibility",
     "Exclusion list is longer than 88% of peer trials",
     "Getz 2016 amendment drivers", "Review exclusions that peers do not use."),
    (r"sample size|statistical hypothes", "C7", "consistency", "critical", "statistics",
     "Stated sample size does not match the recomputed value from alpha, power and effect size",
     "ICH E9; SPIRIT 2025 item 18", "Recheck the sample size inputs or update the stated N."),
    (r"abbreviation", "C9", "completeness", "minor", "clerical",
     "Abbreviation used but never defined",
     "ICH M11 general", "Add the abbreviation to the list of abbreviations."),
    (r"synopsis|protocol summary", "C4", "consistency", "major", "design",
     "Age range in the synopsis differs from the eligibility criteria",
     "ICH M11 1.1, 5.1", "Make the synopsis age range match the inclusion criteria."),
]


def _anchor(pdf: pymupdf.Document, section: Section) -> Where | None:
    """First body line of the section that PyMuPDF can locate on the page."""
    for raw in section.text.split("\n"):
        quote = re.sub(r"\s+", " ", raw).strip()
        if len(quote) < 30 or not re.search(r"[a-z]{3}", quote):
            continue
        quote = quote[:90].rsplit(" ", 1)[0]
        for page_no in range(section.page_start, section.page_end + 1):
            hits = pdf[page_no - 1].search_for(quote)
            if hits:
                r = hits[0]
                for h in hits[1:]:
                    if h.y0 - r.y1 < 4:
                        r |= h
                bbox = [round(v, 1) for v in (r.x0, r.y0, r.x1, r.y1)]
                return Where(section=section.title, page=page_no, bbox=bbox, quote=quote)
    return None


def build(path: str) -> dict:
    pdf = pymupdf.open(path)
    sections = [s for s in find_sections(read_pdf(path)) if s.text]
    issues = []
    for pattern, check_id, category, severity, amend, title, ref, fix in TEMPLATES:
        section = next((s for s in sections if re.search(pattern, s.title, re.I)), None)
        where = _anchor(pdf, section) if section else None
        if not where:
            continue
        issues.append(Issue(
            id=f"iss_{len(issues) + 1:02d}", check_id=check_id, source="rule", category=category,
            severity=severity, title=title, where=where,
            why=Why(explanation=f"Mock issue anchored to real text in {where.section}.",
                    standard_ref=ref, amendment_category=amend),
            fix=Fix(suggestion=fix), confidence=0.9, verified=True,
        ))
    return {"total": len(issues), "items": [i.model_dump() for i in issues]}
