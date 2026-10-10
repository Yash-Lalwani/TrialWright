import asyncio
import re
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz

from preflight.graph.models import Arm, Criterion, Endpoint, Meta, NumberFact, Objective, Section, Span, Stats
from preflight.ingest.pdf import Line, PdfDoc

WORD_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "single": 1}
UNIT_WEEKS = {"day": 1 / 7, "week": 1.0, "month": 52 / 12, "year": 52.0}

AGE_RANGE = re.compile(r"\b(\d{2})\s*(?:to|-|–|and)\s*(\d{2,3})\s*years", re.I)
AGE_MIN = re.compile(r"(?:≥|>=|at least|aged)\s*(\d{2})\s*years"
                     r"|\b(\d{2})\s*years(?: of age)?,? (?:or|and) (?:older|above)", re.I)
AGE_MAX = re.compile(r"(?:≤|<=|no older than|up to|not older than)\s*(\d{2,3})\s*years", re.I)
SAMPLE = re.compile(
    r"(?:approximately|total of|a total of|enroll?|randomi[sz]e)\s+(?:approximately\s+)?(\d{2,5})\s+"
    r"(?:participants|patients|subjects)"
    r"|sample size (?:of|is|will be)\s+(?:approximately\s+)?(\d{2,5})"
    r"|number of (?:subjects|patients|participants)[a-z ]{0,30}? is\s+(?:approximately\s+)?(\d{2,5})", re.I)
RATIO = re.compile(r"\b(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?\b")
ARMS = re.compile(r"\b(one|two|three|four|five|six|\d)[- ](?:treatment )?arms?\b", re.I)
DOSE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg/kg|mg/m2|mg/m²|mg|mcg|µg|μg|g)\b(?!/dL|/L)", re.I)
DURATION = re.compile(r"\b(\d+(?:\.\d+)?)\s*(week|month|year)s?\b", re.I)
XREF = re.compile(r"\b(?:see|refer to|described in|detailed in|per|in)\s+(Section|Appendix)\s+(\d+(?:\.\d+)*|[A-Z]\b)",
                  re.I)
ABBR_DEF = re.compile(r"([A-Za-z][A-Za-z\-]+(?:\s+[A-Za-z\-]+){0,7})\s+\(([A-Z][A-Za-z0-9\-]*[A-Z0-9]s?)\)")
ABBR_USE = re.compile(r"\b([A-Z][A-Z0-9\-]*[A-Z0-9])\b")
NOT_ABBR = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "USA", "UK", "OR", "AND", "NOT", "NO", "N/A",
            "AGE", "AT", "ALL", "FOR", "THE", "OF", "TO", "IN", "ON", "BY", "IF", "AS", "IS", "BE", "AN", "A"}


def _span(line: Line) -> Span:
    return Span(page=line.page, bbox=line.bbox, quote=line.text)


def _weeks(value: float, unit: str) -> float:
    return round(value * UNIT_WEEKS[unit.lower().rstrip("s")], 2)


SKIP_TITLES = re.compile(r"amendment|summary of changes|acceptance|signature|informed consent form|reference", re.I)


def body_lines(parts: list[tuple[Section, list[Line]]]) -> list[Line]:
    """Lines that state this protocol's own design: no background literature, references or amendment history."""
    lines, top = [], None
    for section, body in parts:
        numbered = section.title[:1].isdigit() or section.title.lower().startswith("appendix")
        if section.level == 1 and numbered:
            top = section.m11_id
        m11 = section.m11_id or top or ""
        if m11 == "2" or m11.startswith("2.") or m11 == "14" or SKIP_TITLES.search(section.title):
            continue
        lines.extend(body)
    return lines


def extract_numbers(lines: list[Line]) -> list[NumberFact]:
    facts: list[NumberFact] = []

    def add(kind, value, unit, line):
        facts.append(NumberFact(kind=kind, value=value, unit=unit, span=_span(line)))

    for k, ln in enumerate(lines):
        t = ln.text
        low = t.lower()
        nxt = lines[k + 1].text.lower() if k + 1 < len(lines) else ""
        if re.search(r"\bage\b|\baged\b|years of age|years old", low) and not re.search(
                r"amenorrh|menopaus|childbearing|female|women|median|mean age|clearance|covariate|range", low):
            if m := AGE_RANGE.search(t):
                add("age_min", float(m.group(1)), "years", ln)
                add("age_max", float(m.group(2)), "years", ln)
            else:
                if m := AGE_MIN.search(t):
                    add("age_min", float(m.group(1) or m.group(2)), "years", ln)
                if m := AGE_MAX.search(t):
                    add("age_max", float(m.group(1)), "years", ln)
        sample_context = re.search(r"enrol|randomi|planned|sample size|number of (subjects|patients|participants)",
                                   f"{low} {nxt}")
        if sample_context and not re.search(r"\bpk\b|pharmacokinetic|subset|substudy|evaluable|achieves|power",
                                            low) and (m := SAMPLE.search(t)):
            add("sample_size", float(next(g for g in m.groups() if g)), None, ln)
        if "ratio" in low and re.search(r"random|allocation", low):
            m = RATIO.search(t)
        else:
            m = re.search(r"randomi[sz]ed\s*\(?\s*(\d{1,2}):(\d{1,2})\b", t)
        if m:
            add("ratio", ":".join(g for g in m.groups() if g), None, ln)
        if m := ARMS.search(t):
            word = m.group(1).lower()
            add("arms", float(WORD_NUMS.get(word) or int(word)), None, ln)
        if re.search(r"\b(dose|dosing|administered|mg)\b", low) and "mg" in low:
            for m in DOSE.finditer(t):
                add("dose", float(m.group(1)), m.group(2), ln)
        if not re.search(r"\bage\b|years old|years of age", low):
            for m in DURATION.finditer(t):
                add("duration_weeks", _weeks(float(m.group(1)), m.group(2)), "weeks", ln)
    return facts


def age_limits(facts: list[NumberFact], sections: list[Section]) -> tuple[float | None, float | None]:
    """Prefer ages stated inside the inclusion criteria pages."""
    incl = [s for s in sections if s.m11_id == "5.2"] or [s for s in sections if "inclusion" in s.title.lower()]
    pages = {p for s in incl for p in range(s.page_start, s.page_end + 1)}

    def pick(kind):
        vals = [f for f in facts if f.kind == kind]
        preferred = [f for f in vals if f.span.page in pages] or vals
        return float(preferred[0].value) if preferred else None

    return pick("age_min"), pick("age_max")


def extract_xrefs(lines: list[Line]) -> list[dict]:
    refs = []
    for ln in lines:
        for m in XREF.finditer(ln.text):
            target = f"{m.group(1).title()} {m.group(2)}"
            refs.append({"text": m.group(0), "target": target, "span": _span(ln).model_dump()})
    return refs


def extract_abbreviations(doc: PdfDoc, sections: list[Section]) -> dict:
    defined: dict[str, str] = {}
    glossary = [s for s in sections if s.m11_id == "13" or "abbreviation" in s.title.lower()]
    for s in glossary:
        for row in s.text.split("\n"):
            if m := re.match(r"^([A-Z][A-Za-z0-9\-/]*[A-Z0-9])\s+(.{3,})$", row):
                defined.setdefault(m.group(1), m.group(2).strip())
    used: dict[str, int] = {}
    for ln in doc.lines:
        for m in ABBR_DEF.finditer(ln.text):
            abbr, words = m.group(2), m.group(1).split()
            long_form = " ".join(words[-len(abbr.rstrip("s")):])
            defined.setdefault(abbr, long_form)
        letters = [c for c in ln.text if c.isalpha()]
        if not letters or sum(c.isupper() for c in letters) / len(letters) > 0.4:
            continue
        for m in ABBR_USE.finditer(ln.text):
            a = m.group(1)
            word_like = a.isalpha() and len(a) >= 6
            if (a not in NOT_ABBR and sum(c.isupper() for c in a) >= 2 and len(a) <= 8 and not word_like
                    and len(re.findall(r"\d", a)) <= 2):
                used[a] = used.get(a, 0) + 1
    return {"defined": defined, "used": sorted(used)}


PHASE = re.compile(r"\bphase\s+(I{1,3}V?|IV|[1-4])(?:\s*/\s*(I{1,3}|[1-4]))?\b", re.I)
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}


def _title(lines: list[Line], body_size: float) -> str:
    """Longest block of adjacent same-size lines on the first pages that names a study or trial."""
    blocks: list[list[Line]] = []
    for ln in lines:
        if ln.size < body_size:
            blocks.append([])
            continue
        if m := re.match(r"^(?:protocol\s+)?title:\s*(.+)", ln.text, re.I):
            ln = Line(ln.page, m.group(1), ln.bbox, ln.size, ln.bold)
        elif ":" in ln.text:
            continue
        prev = blocks[-1][-1] if blocks and blocks[-1] else None
        adjacent = prev and prev.page == ln.page and -3 <= ln.bbox[1] - prev.bbox[3] < ln.size
        if adjacent and abs(prev.size - ln.size) <= 1.5:
            blocks[-1].append(ln)
        else:
            blocks.append([ln])

    def rank(block):
        text = " ".join(ln.text for ln in block)
        styled = sum(ln.bold or ln.size > body_size + 0.5 for ln in block) / len(block)
        return (bool(re.search(r"\b(study|trial)\b", text, re.I)), styled > 0.5, len(text) < 400, len(text))

    blocks = [b for b in blocks if b]
    if not blocks:
        return ""
    title = " ".join(ln.text for ln in max(blocks, key=rank))
    title = re.sub(r"^protocol\s+(title:\s*)?", "", title, flags=re.I)
    return title.title() if title.isupper() else title


def _first_label(texts: list[str], options: list[tuple[str, str]]) -> str | None:
    for text in texts:
        for pattern, label in options:
            if re.search(pattern, text, re.I):
                return label
    return None


def extract_meta(doc: PdfDoc, sections: list[Section]) -> Meta:
    first = [ln for ln in doc.lines if ln.page <= 3]
    head_text = " ".join(ln.text for ln in first)
    full = " ".join(ln.text for ln in doc.lines[:4000])

    title = _title(first, doc.body_size)

    phase = None
    if m := PHASE.search(head_text) or PHASE.search(full):
        parts = [ROMAN.get(g.upper(), g) for g in m.groups() if g]
        phase = "/".join(f"PHASE{p}" for p in parts)

    masking = _first_label([title, head_text, full], [
        (r"double[- ]blind", "DOUBLE"), (r"single[- ]blind", "SINGLE"), (r"open[- ]label", "NONE")])
    allocation = _first_label([title, head_text, full], [
        (r"non[- ]?randomi[sz]ed", "NON_RANDOMIZED"), (r"randomi[sz]ed", "RANDOMIZED")])
    nct = re.search(r"\bNCT\d{8}\b", full)
    return Meta(title=title, nct_id=nct.group(0) if nct else None, phase=phase, condition=None, sponsor=None,
                masking=masking, allocation=allocation, n_arms=None, ratio=None)


# --- LLM extraction (section-scoped) ---

class _EndpointOut(BaseModel):
    text: str
    measure: str
    timepoints_weeks: list[float] = []
    quote: str


class _ObjectiveOut(BaseModel):
    level: Literal["primary", "secondary", "exploratory"]
    text: str
    quote: str
    endpoints: list[_EndpointOut] = []


class _ObjectivesOut(BaseModel):
    objectives: list[_ObjectiveOut]


class _Threshold(BaseModel):
    test: str
    op: str
    value: float
    unit: str | None = None


class _CriterionOut(BaseModel):
    kind: Literal["inclusion", "exclusion"]
    text: str
    quote: str
    thresholds: list[_Threshold] = []


class _CriteriaOut(BaseModel):
    criteria: list[_CriterionOut]


class _AnalysisOut(BaseModel):
    endpoint_ids: list[str]
    method: str
    quote: str


class _StatsOut(BaseModel):
    sample_size: int | None = None
    alpha: float | None = None
    sided: int | None = None
    power: float | None = None
    effect_size: float | None = None
    effect_type: Literal["mean_diff_sd", "proportions", "hazard_ratio"] | None = None
    control_rate: float | None = None
    dropout: float | None = None
    analyses: list[_AnalysisOut] = []


class _ArmsOut(BaseModel):
    condition: str | None = None
    sponsor: str | None = None
    arms: list[Arm] = []


MAX_CHARS = 14000
QUOTE_RULE = "Every 'quote' must be copied verbatim from the text (one sentence or phrase, under 200 characters)."


def effective_parts(parts: list[tuple[Section, list[Line]]], prefixes: tuple[str, ...]) -> list[Line]:
    """Body lines of sections whose own or inherited M11 id starts with one of the prefixes."""
    stack: list[tuple[int, str | None]] = []
    lines = []
    for section, body in parts:
        while stack and stack[-1][0] >= section.level:
            stack.pop()
        inherited = next((m for _, m in reversed(stack) if m), None)
        m11 = section.m11_id or inherited
        stack.append((section.level, section.m11_id))
        if m11 and any(m11 == p or m11.startswith(p + ".") for p in prefixes):
            lines.extend(body)
    return lines


def locate(quote: str, lines: list[Line]) -> Span:
    """Span of the line that best contains the quote."""
    if not lines:
        return Span(page=1, bbox=None, quote=quote)
    probe = quote[:120].lower()
    best = max(lines, key=lambda ln: fuzz.partial_ratio(probe, ln.text.lower()))
    return Span(page=best.page, bbox=best.bbox, quote=quote)


def _text(lines: list[Line]) -> str:
    out, size = [], 0
    for ln in lines:
        piece = f"[p{ln.page}] {ln.text}" if not out or out[-1].split("]")[0] != f"[p{ln.page}" else ln.text
        size += len(piece) + 1
        if size > MAX_CHARS:
            break
        out.append(piece)
    return "\n".join(out)


async def extract_llm(parts: list[tuple[Section, list[Line]]]) -> dict:
    from preflight.llm.client import complete_json

    obj_lines = effective_parts(parts, ("3",)) or effective_parts(parts, ("1.1",))
    crit_lines = effective_parts(parts, ("5.2", "5.3"))
    stats_lines = effective_parts(parts, ("10",))
    design_lines = effective_parts(parts, ("1.1", "4.1", "6")) or effective_parts(parts, ("4",))

    async def ask(step, system, lines, schema, extra=""):
        if not lines:
            return None
        return await complete_json(step, f"{system} {QUOTE_RULE}", extra + _text(lines), schema)

    objectives_out, inclusion_out, exclusion_out, arms_out = await asyncio.gather(
        ask("extract_objectives",
            "Extract every trial objective and its endpoints. Convert endpoint timepoints to study weeks "
            "(Day 1 = week 0, 'Cycle 3 Day 1' of 3-week cycles = week 6, 6 months = 26 weeks).",
            obj_lines, _ObjectivesOut),
        ask("extract_inclusion",
            "Extract every inclusion criterion (kind 'inclusion'). For lab or numeric limits give thresholds "
            "like {test: 'ANC', op: '>=', value: 1.5, unit: '10^9/L'}. Keep each text under 300 characters.",
            effective_parts(parts, ("5.2",)), _CriteriaOut),
        ask("extract_exclusion",
            "Extract every exclusion criterion (kind 'exclusion'). For lab or numeric limits give thresholds "
            "like {test: 'ANC', op: '<', value: 1.5, unit: '10^9/L'}. Keep each text under 300 characters.",
            effective_parts(parts, ("5.3",)), _CriteriaOut),
        ask("extract_design",
            "Extract the condition studied, the sponsor and the treatment arms (name, type such as "
            "experimental/active comparator/placebo, dose, route, frequency, duration in weeks).",
            design_lines, _ArmsOut),
    )
    criteria_out = _CriteriaOut(criteria=[*(inclusion_out.criteria if inclusion_out else []),
                                          *(exclusion_out.criteria if exclusion_out else [])])
    # Endpoint ids are assigned in this order by _assemble; the stats call links analyses to them.
    ep_list = [e for o in (objectives_out.objectives if objectives_out else []) for e in o.endpoints]
    catalog = "\n".join(f"ep_{i}: {e.measure} ({e.text[:100]})" for i, e in enumerate(ep_list, 1))
    stats_out = await ask(
        "extract_stats",
        "Extract the sample size inputs (alpha as a decimal, power as a decimal, sided 1 or 2, effect size, "
        "control rate, dropout) and every analysis method. For each analysis list the ids of the endpoints it "
        "covers, chosen from the endpoint list. Use null when not stated.",
        stats_lines, _StatsOut, extra=f"Endpoints:\n{catalog or 'none'}\n\nStatistics text:\n")
    return _assemble(objectives_out, criteria_out, stats_out, arms_out, obj_lines, crit_lines, stats_lines)


def _assemble(objectives_out, criteria_out, stats_out, arms_out, obj_lines, crit_lines, stats_lines) -> dict:
    objectives, endpoints = [], []
    for o in objectives_out.objectives if objectives_out else []:
        ids = []
        for e in o.endpoints:
            eid = f"ep_{len(endpoints) + 1}"
            ids.append(eid)
            endpoints.append(Endpoint(id=eid, text=e.text, measure=e.measure, timepoints_weeks=e.timepoints_weeks,
                                      analysis_ids=[], span=locate(e.quote, obj_lines)))
        objectives.append(Objective(id=f"obj_{len(objectives) + 1}", level=o.level, text=o.text,
                                    endpoint_ids=ids, span=locate(o.quote, obj_lines)))

    criteria = []
    counts = {"inclusion": 0, "exclusion": 0}
    for c in criteria_out.criteria if criteria_out else []:
        counts[c.kind] += 1
        criteria.append(Criterion(id=f"{c.kind[:3]}_{counts[c.kind]}", kind=c.kind, text=c.text,
                                  thresholds=[t.model_dump() for t in c.thresholds], span=locate(c.quote, crit_lines)))

    s = stats_out or _StatsOut()
    analyses = []
    by_id = {e.id: e for e in endpoints}
    for a in s.analyses:
        for eid in [e for e in a.endpoint_ids if e in by_id] or [None]:
            aid = f"ana_{len(analyses) + 1}"
            if eid:
                by_id[eid].analysis_ids.append(aid)
            analyses.append({"id": aid, "endpoint_id": eid, "method": a.method,
                             "span": locate(a.quote, stats_lines).model_dump()})
    stats = Stats(**s.model_dump(exclude={"analyses"}), analyses=analyses)
    arms = arms_out.arms if arms_out else []
    return {"objectives": objectives, "endpoints": endpoints, "criteria": criteria, "stats": stats, "arms": arms,
            "condition": arms_out.condition if arms_out else None, "sponsor": arms_out.sponsor if arms_out else None}
