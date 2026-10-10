import re

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import ProtocolGraph, Span

MASKING = {"DOUBLE": r"double[- ]blind", "SINGLE": r"single[- ]blind", "NONE": r"open[- ]label"}
PHASE = re.compile(r"\bphase\s+(I{1,3}V?|IV|[1-4])(?:\s*/\s*(I{1,3}|[1-4]))?\b", re.I)
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}


def _design_sections(graph: ProtocolGraph):
    """Sections that describe this trial (synopsis, objectives, design, population, treatment, statistics)."""
    return [s for s in graph.sections
            if s.m11_id and s.m11_id.split(".")[0] in {"1", "3", "4", "5", "6", "10"} and s.m11_id != "1.3"]


def _span(section, pattern) -> Span | None:
    """First line using the pattern about this trial; 'a double-blind study' describes some other or hypothetical
    trial, so mentions after 'a'/'an'/'other' are skipped."""
    for line in section.text.split("\n"):
        m = re.search(pattern, line, re.I)
        if m and not re.search(r"\b(a|an|other|another|previous|prior)\s+$", line[:m.start()], re.I):
            return Span(page=section.page_start, bbox=None, quote=line.strip()[:200])
    return None


@check(id="C5", category="consistency", amendment_category="design",
       standard_ref="ICH M11 4.1, 6.4; SPIRIT 2025 items 16, 17", severity="major")
def design_logic(graph: ProtocolGraph, ctx: CheckContext):
    issues = []
    sections = _design_sections(graph)
    all_text = "\n".join(s.text for s in graph.sections)

    if graph.meta.masking in ("DOUBLE", "SINGLE") and not re.search(r"unblind|break(ing)? the blind|code break",
                                                                    all_text, re.I):
        issues.append(issue(
            "C5", f"{graph.meta.masking.title()}-blind trial has no unblinding procedure",
            where(graph, None, section="Trial design"),
            "The protocol says the trial is blinded but never describes how or when the blind is broken "
            "(emergency unblinding, who holds the codes).",
            fix="Add an emergency unblinding procedure (who can unblind, how, and how it is documented).",
            severity="critical"))

    found = {}
    for s in sections:
        for label, pattern in MASKING.items():
            if label not in found and (span := _span(s, pattern)):
                found[label] = (s, span)
    if len(found) > 1 and graph.meta.masking in found:
        main_s, main_span = found[graph.meta.masking]
        for label, (s, span) in found.items():
            if label == graph.meta.masking:
                continue
            issues.append(issue(
                "C5", f"Masking is described as both {graph.meta.masking.lower()} and {label.lower()}",
                where(graph, span, s.title),
                f"The design is '{graph.meta.masking.lower()}' in {main_s.title} but '{label.lower()}' "
                f"appears in {s.title}.",
                fix="Use one masking description throughout the protocol.", related=[where(graph, main_span,
                                                                                           main_s.title)]))

    phases = {}
    for s in sections:
        for line in s.text.split("\n"):
            own = re.search(r"\b(this|the present|the current)\s+(study|trial)\b|^(study\s+)?phase\s*:", line, re.I)
            if own and (m := PHASE.search(line)):
                label = "/".join(ROMAN.get(g.upper(), g) for g in m.groups() if g)
                phases.setdefault(label, (s, Span(page=s.page_start, bbox=None, quote=line.strip()[:200])))
    stated = (graph.meta.phase or "").replace("PHASE", "")
    if stated and len(phases) > 1 and stated in phases:
        for label, (s, span) in phases.items():
            if label != stated and label not in stated.split("/"):
                issues.append(issue(
                    "C5", f"Phase is stated as Phase {stated} and Phase {label}", where(graph, span, s.title),
                    f"The protocol is Phase {stated}, but {s.title} says Phase {label}.",
                    fix="Use the same phase label everywhere.", confidence=0.8))
    return issues
