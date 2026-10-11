# ruff: noqa: E501
"""E3 + E7: turn a design brief into a checked protocol draft.

Steps (progress events): precedent -> sample_size -> draft_sections -> build_graph -> self_check -> burden.

* precedent: the most similar registered trials (burden.precedent), found from the brief alone.
* sample_size: the same calculator the checker uses (checks.sample_size.calc_sample_size), never the LLM.
* draft_sections: M11-ordered sections. The LLM may use ONLY the brief and the precedent rows; unknown facts become
  "[TBD: ...]" markers, and a citation survives only if it is one of the precedent NCT ids. Without an LLM (no key, no
  cache) every section falls back to a plain template built from the brief, so a draft is always produced.
* build_graph: a ProtocolGraph is built from the drafted text (criteria from bullets, arms and stats from the brief).
  Spans use SYNTHETIC page numbers (one page per drafted section), because a draft has no PDF.
* self_check: the draft goes through the same rules a real protocol does (check_graph, rules_only). Sections the
  brief does not support are NOT drafted, so completeness will list them as missing; that is accurate, not a bug.
* burden: no schedule is drafted (it would be invented), so the burden report is empty by construction.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from preflight import burden
from preflight.checks.sample_size import calc_sample_size, parse_ratio
from preflight.graph.models import Arm, Criterion, Endpoint, Meta, NumberFact, Objective, ProtocolGraph, Section, Span, Stats
from preflight.pipeline import check_graph

from .models import Brief, DraftSection, SampleSizeOut

Progress = Callable[[str, str, str], Awaitable[None]]
NCT = re.compile(r"\bNCT\d{8}\b")
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)")

# (m11_id, title, what to write)
PLAN = [
    ("2.1", "Purpose of Trial", "2 to 3 short paragraphs: the unmet need and why this trial is being run. Cite similar registered trials where useful."),
    ("3", "Trial Objectives and Associated Estimands", "A '### 3.1 Primary Objective' with one primary endpoint and its timepoint, then '### 3.2 Secondary Objectives' with at most 3 secondary objectives marked [TBD] if the brief does not give them."),
    ("4.1", "Description of Trial Design", "Phase, design (randomisation, masking, comparator), arms, planned duration. Only what the brief states."),
    ("5.2", "Inclusion Criteria", "A bulleted list, one criterion per bullet, starting from the brief's population. Use the precedent trials' typical age and ECOG limits as guidance and cite them."),
    ("5.3", "Exclusion Criteria", "A bulleted list, one criterion per bullet, of standard safety exclusions for this condition and drug class. Mark any criterion that needs a medical decision with [TBD]."),
    ("6.1", "Trial Intervention", "Name, dose, route and schedule of the intervention and the comparator, exactly as in the brief; [TBD] for anything the brief omits."),
]


_LIMIT = asyncio.Semaphore(3)


class _Out(BaseModel):
    markdown: str


def brief_graph(brief: Brief) -> ProtocolGraph:
    """A near-empty graph that carries only what the brief says, enough for peer search and precedent."""
    arms = [Arm(name=brief.intervention, type="experimental", dose=None, route=None, frequency=None, duration_weeks=brief.duration_weeks)]
    if brief.comparator:
        arms.append(Arm(name=brief.comparator, type="active_comparator", dose=None, route=None, frequency=None, duration_weeks=brief.duration_weeks))
    return ProtocolGraph(
        protocol_id="drf_brief", meta=Meta(title=brief.primary_question, nct_id=None, phase=brief.phase, condition=brief.condition, sponsor=None,
                                            masking=None, allocation=None, n_arms=len(arms), ratio=brief.ratio),
        sections=[], objectives=[], endpoints=[], criteria=[], min_age=None, max_age=None, arms=arms, soa=None,
        stats=Stats(sample_size=None, alpha=brief.alpha, sided=2, power=brief.power, effect_size=None, effect_type=None, control_rate=None, dropout=brief.dropout, analyses=[]),
        numbers=[], xrefs=[], abbreviations={"defined": {}, "used": []})


def compute_sample_size(brief: Brief) -> SampleSizeOut | None:
    e = brief.expected_effect
    effect, control = {"proportions": (e.treatment, e.control), "mean_diff_sd": (e.effect, None), "hazard_ratio": (e.effect, e.event_rate)}[e.type]
    if effect is None:
        return None
    r = calc_sample_size(e.type, effect, brief.alpha, brief.power, 2, control, brief.dropout, parse_ratio(brief.ratio))
    if r is None:
        return None
    inputs = {"alpha": brief.alpha, "power": brief.power, "dropout": brief.dropout, "ratio": brief.ratio,
              **{k: v for k, v in e.model_dump().items() if v is not None}}
    return SampleSizeOut(n_total=r.n_total_enrolled, n_per_arm=round(r.n_total_enrolled / (1 + parse_ratio(brief.ratio))), method=r.method, inputs=inputs)


def _precedent_facts(table) -> str:
    return "\n".join(f"- {r.nct_id}: {r.title[:90]} | primary: {r.primary_endpoint[:80]} ({r.primary_timeframe}) | eligibility: {', '.join(r.key_eligibility)} | n={r.enrollment}"
                     for r in table.rows[:8]) or "(no similar trials found)"


def _template(brief: Brief, m11_id: str, title: str) -> str:
    """Offline fallback: only the brief's own words, everything else TBD."""
    arms = f"{brief.intervention}" + (f" versus {brief.comparator}" if brief.comparator else "")
    return {
        "2.1": f"This {brief.phase} trial in {brief.condition} addresses: {brief.primary_question}\n\n[TBD: unmet need and rationale]",
        "3": f"### 3.1 Primary Objective\n{brief.primary_question}\n\n### 3.2 Secondary Objectives\n[TBD: secondary objectives]",
        "4.1": f"A {brief.phase} study of {arms}, with allocation {brief.ratio}. Planned duration: {brief.duration_weeks:g} weeks." if brief.duration_weeks else f"A {brief.phase} study of {arms}, with allocation {brief.ratio}. [TBD: duration]",
        "5.2": f"- {brief.population}\n- [TBD: age and performance status limits]\n- [TBD: disease criteria]",
        "5.3": "- [TBD: safety exclusions to be set by the medical team]",
        "6.1": f"- Experimental: {brief.intervention}" + (f"\n- Comparator: {brief.comparator}" if brief.comparator else "") + "\n- [TBD: dose, route and schedule where not stated]",
    }[m11_id]


async def _write_section(brief: Brief, table, m11_id: str, title: str, instruction: str) -> DraftSection:
    from preflight.llm.client import LLMCacheMiss, LLMUnavailable, complete_json

    allowed = {r.nct_id for r in table.rows}
    system = ("You draft ONE section of a clinical trial protocol in the ICH M11 style. Use ONLY the design brief and the "
              "similar-trials list given. Never invent numbers, doses, drugs or criteria that are not in them; where a fact is "
              "missing write [TBD: what is needed]. You may cite a similar trial inline as its NCT id (e.g. NCT01234567), only from the list. "
              "Return markdown for the section body, without the section heading.")
    user = f"Section: {m11_id} {title}\nTask: {instruction}\n\nBrief:\n{brief.model_dump_json(indent=1)}\n\nSimilar registered trials:\n{_precedent_facts(table)}"
    text, source = None, "template"
    for attempt in range(2):          # one retry: a transient provider error under parallel calls is not "no LLM"
        try:
            async with _LIMIT:
                out = await complete_json(f"draft_{m11_id}", system, user, _Out)
            text, source = out.markdown.strip(), "llm"
            break
        except LLMCacheMiss:
            break
        except LLMUnavailable:
            await asyncio.sleep(0.5 * attempt)
    if text is None:
        text = _template(brief, m11_id, title)
    cites = sorted(set(NCT.findall(text)) & allowed)
    text = NCT.sub(lambda m: m.group(0) if m.group(0) in allowed else "[unverified citation removed]", text)
    return DraftSection(m11_id=m11_id, title=title, markdown=text, citations=cites, source=source)


def sample_size_section(size: SampleSizeOut | None, brief: Brief) -> DraftSection:
    if size is None:
        text = "[TBD: the expected effect in the brief is not enough to compute a sample size]"
    else:
        i = size.inputs
        text = (f"A total of {size.n_total} participants ({size.n_per_arm} per arm) will be randomised {brief.ratio}. Method: {size.method}, "
                f"two-sided alpha {brief.alpha:g}, power {brief.power:g}"
                + (f", allowing for {brief.dropout:.0%} dropout" if brief.dropout else "") + f". Assumptions: {', '.join(f'{k} {v}' for k, v in i.items() if k in ('control', 'treatment', 'effect', 'event_rate'))}.")
    return DraftSection(m11_id="10.11", title="Sample Size Determination", markdown=text, citations=[], source="calculation")


def build_graph(brief: Brief, sections: list[DraftSection], size: SampleSizeOut | None) -> ProtocolGraph:
    g = brief_graph(brief)
    secs, criteria, numbers = [], [], []
    for page, s in enumerate(sections, 1):
        secs.append(Section(id=f"sec_{page}", m11_id=s.m11_id, title=f"{s.m11_id} {s.title}", level=1 if "." not in s.m11_id else 2, page_start=page, page_end=page, text=s.markdown))
        if s.m11_id in ("5.2", "5.3"):
            kind = "inclusion" if s.m11_id == "5.2" else "exclusion"
            for n, line in enumerate(s.markdown.splitlines()):
                if m := BULLET.match(line):
                    criteria.append(Criterion(id=f"crit_{kind[:3]}{n}", kind=kind, text=m.group(1), thresholds=[], span=Span(page=page, bbox=None, quote=m.group(1)[:200])))
    ep = Endpoint(id="ep_1", text=brief.primary_question, measure=brief.primary_question, timepoints_weeks=[brief.duration_weeks] if brief.duration_weeks else [], analysis_ids=[], span=Span(page=2, bbox=None, quote=brief.primary_question))
    obj = Objective(id="obj_1", level="primary", text=brief.primary_question, endpoint_ids=["ep_1"], span=Span(page=2, bbox=None, quote=brief.primary_question))
    stats = g.stats.model_copy()
    if size:
        e = brief.expected_effect
        stats = stats.model_copy(update={"sample_size": size.n_total, "effect_type": e.type, "dropout": brief.dropout,
                                         "effect_size": e.treatment if e.type == "proportions" else e.effect,
                                         "control_rate": e.control if e.type == "proportions" else e.event_rate})
        page = next(i for i, s in enumerate(sections, 1) if s.m11_id == "10.11")
        numbers.append(NumberFact(kind="sample_size", value=size.n_total, unit=None, span=Span(page=page, bbox=None, quote=f"A total of {size.n_total} participants")))
    return g.model_copy(update={"sections": secs, "criteria": criteria, "endpoints": [ep], "objectives": [obj], "stats": stats, "numbers": numbers})


async def _noop(step: str, status: str, message: str) -> None:
    return None


async def draft_from_brief(brief: Brief, progress: Progress = _noop) -> dict:
    graph0 = brief_graph(brief)
    peers = await asyncio.to_thread(burden.find_peers, graph0)
    table = await asyncio.to_thread(burden.precedent, graph0, peers)
    await progress("precedent", "done", f"{len(table.rows)} similar trials")

    size = compute_sample_size(brief)
    await progress("sample_size", "done", f"{size.n_total} participants" if size else "not computable from the brief")

    drafted = await asyncio.gather(*(_write_section(brief, table, *p) for p in PLAN))
    sections = sorted([*drafted, sample_size_section(size, brief)], key=lambda s: [int(x) for x in s.m11_id.split(".")])
    await progress("draft_sections", "done", f"{len(sections)} sections, {sum(s.source == 'llm' for s in sections)} written by the model")

    graph = build_graph(brief, sections, size)
    await progress("build_graph", "done", f"{len(graph.criteria)} criteria")

    result = await check_graph(graph, mode="rules_only")
    await progress("self_check", "done", f"score {result.score.overall}, {len(result.issues)} issues")

    report = burden.compute_burden(graph, peers)
    await progress("burden", "done", "no schedule drafted; burden empty")
    return {"status": "complete", "brief": brief.model_dump(), "precedent": table.model_dump(),
            "sample_size": size.model_dump() if size else None, "sections": [s.model_dump() for s in sections],
            "burden": report.model_dump(), "self_check": {"score": result.score.model_dump(), "issues": [i.model_dump() for i in result.issues]},
            "llm_used": any(s.source == "llm" for s in sections)}      # llm_used is ADDITIVE
