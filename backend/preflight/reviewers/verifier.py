import re

import pymupdf
from rapidfuzz import fuzz

from preflight.graph.issues import Fix, Issue, Where, Why
from preflight.graph.models import ProtocolGraph
from preflight.ingest.pdf import clean_text
from preflight.reviewers.committee import Finding

MIN_GROUNDING = 90
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")


def normalize(text: str) -> str:
    text = clean_text(text).lower()
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text)


def page_texts(graph: ProtocolGraph, pdf_path: str | None) -> dict[int, str]:
    """Text per page: from the PDF when available, otherwise from section text (drafts, JSON input)."""
    if pdf_path and pdf_path.lower().endswith(".pdf"):
        with pymupdf.open(pdf_path) as doc:
            return {i: normalize(p.get_text()) for i, p in enumerate(doc, 1)}
    pages: dict[int, str] = {}
    for s in graph.sections:
        for p in range(s.page_start, s.page_end + 1):
            pages[p] = pages.get(p, "") + " " + normalize(s.text)
    return pages


PAGE_SLACK = (3, 12)  # reviewers see one page marker per section, so a quote can sit a few pages after the cited one


def quote_text(finding: Finding) -> str:
    """The checkable part of a quote: for a rendered SoA row ('Urinalysis | X | X') only the procedure name."""
    return normalize(finding.quote.split("|")[0])


def locate_page(finding: Finding, pages: dict[int, str], soa_names: set[str] | None = None,
                soa_pages: range | None = None) -> int | None:
    """Page near the cited one where the quote really is (partial_ratio >= 90), preferring the cited page.
    Short quotes match almost anywhere, so under 4 words only an exact SoA procedure name on an SoA page counts."""
    quote = quote_text(finding)
    lo, hi = finding.page - PAGE_SLACK[0], finding.page + PAGE_SLACK[1]
    if len(quote.split()) < 4:
        if not (soa_names and quote in soa_names and soa_pages):
            return None
        lo, hi = soa_pages.start, soa_pages.stop - 1
    scored = [(fuzz.partial_ratio(quote, t), -abs(p - finding.page), p) for p, t in pages.items() if lo <= p <= hi]
    best = max(scored, default=None)
    return best[2] if best and best[0] >= MIN_GROUNDING else None


def grounded(finding: Finding, pages: dict[int, str]) -> bool:
    return locate_page(finding, pages) == finding.page


def _soa_scope(graph: ProtocolGraph) -> tuple[set[str], range | None]:
    if not graph.soa or not graph.soa.span:
        return set(), None
    names = {normalize(p.name) for p in graph.soa.procedures}
    soa_sections = [s for s in graph.sections if s.page_start <= graph.soa.span.page <= s.page_end]
    end = max((s.page_end for s in soa_sections), default=graph.soa.span.page)
    return names, range(graph.soa.span.page, end + 3)


def known_numbers(graph: ProtocolGraph) -> set[float]:
    nums = {float(n.value) for n in graph.numbers if isinstance(n.value, (int, float))}
    for n in graph.numbers:
        if isinstance(n.value, str):
            nums |= {float(x) for x in NUMBER.findall(n.value)}
    s = graph.stats
    nums |= {float(v) for v in (s.sample_size, s.alpha, s.power, s.effect_size, s.control_rate, s.dropout) if v}
    nums |= {float(w) for e in graph.endpoints for w in e.timepoints_weeks}
    if graph.soa:
        nums |= {float(v.study_day) for v in graph.soa.visits if v.study_day is not None}
    return nums


def numbers_ok(finding: Finding, graph: ProtocolGraph, known: set[float]) -> bool:
    """Every number the explanation states must appear in the quote or in the extracted graph."""
    quoted = {float(x) for x in NUMBER.findall(finding.quote)}
    stated = {float(x) for x in NUMBER.findall(finding.explanation)}
    return all(n in quoted or n in known or n < 2 for n in stated)


def bbox(pdf_path: str | None, page: int, quote: str) -> list[float] | None:
    if not (pdf_path and pdf_path.lower().endswith(".pdf")):
        return None
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page <= len(doc):
            return None
        hits = doc[page - 1].search_for(quote[:80])
    return [round(v, 1) for v in (hits[0].x0, hits[0].y0, hits[0].x1, hits[0].y1)] if hits else None


def verify(findings: list[tuple[str, Finding]], graph: ProtocolGraph,
           pdf_path: str | None) -> tuple[list[Issue], dict]:
    """Drop ungrounded findings; turn the rest into C11 advisory issues."""
    pages = page_texts(graph, pdf_path)
    known = known_numbers(graph)
    issues, dropped = [], 0
    soa_names, soa_pages = _soa_scope(graph)
    used: set[str] = set()
    for role, f in findings:
        page = locate_page(f, pages, soa_names, soa_pages)
        if page is None:
            dropped += 1
            continue
        if quote_text(f) in used:
            dropped += 1  # one quote reused as evidence for several different claims supports none of them
            continue
        used.add(quote_text(f))
        f = f.model_copy(update={"page": page})
        confidence = 0.7 if numbers_ok(f, graph, known) else 0.4
        issues.append(Issue(
            id="", check_id="C11", source=f"ai:{role}", category="advisory", severity="advisory", title=f.title,
            where=Where(section=f.section, page=f.page, bbox=bbox(pdf_path, f.page, f.quote.split("|")[0].strip()),
                        quote=f.quote.split("|")[0].strip() if "|" in f.quote else f.quote),
            why=Why(explanation=f.explanation, standard_ref=None, amendment_category=_amendment(f)),
            fix=Fix(suggestion=f.fix), confidence=confidence, verified=True,
        ))
    return issues, {"ai_findings": len(findings), "dropped_ungrounded": dropped, "shown": len(issues)}



def _amendment(f: Finding) -> str:
    text = f"{f.title} {f.explanation}".lower()
    for key, cat in [("eligib", "eligibility"), ("inclusion", "eligibility"), ("exclusion", "eligibility"),
                     ("visit", "visit_schedule"), ("schedule", "visit_schedule"), ("safety", "safety"),
                     ("endpoint", "endpoints"), ("estimand", "statistics"), ("statist", "statistics"),
                     ("sample size", "statistics"), ("dose", "intervention"), ("design", "design")]:
        if key in text:
            return cat
    return "completeness" if f.category == "completeness" else "clerical"


def attach_fixes(rule_issues: list[Issue], ai_issues: list[Issue]) -> list[Issue]:
    """Rules win: an AI finding on the same page as a rule issue with a similar title gives its fix text to the
    rule issue (when the rule has none) and is dropped. Remaining AI findings stay as advisories."""
    kept = []
    for ai in ai_issues:
        match = next((r for r in rule_issues if r.where.page == ai.where.page
                      and fuzz.token_set_ratio(r.title, ai.title) >= 60), None)
        if match is None:
            kept.append(ai)
        elif match.fix is None and ai.fix:
            match.fix = ai.fix
    return kept
