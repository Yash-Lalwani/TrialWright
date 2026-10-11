import asyncio
import hashlib
import logging
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import BaseModel

from preflight import score
from preflight.checks.completeness import Completeness, compute_completeness
from preflight.checks.registry import CheckContext, run_checks
from preflight.graph.issues import Issue
from preflight.graph.models import ProtocolGraph, Stats
from preflight.ingest import entities
from preflight.ingest.m11_map import map_sections
from preflight.ingest.pdf import read_pdf
from preflight.ingest.sections import split_sections
from preflight.ingest.soa import extract_soa, fill_days_with_llm
from preflight.score import Score

log = logging.getLogger(__name__)


Progress = Callable[[str, str, str], Awaitable[None]]


async def _noop(step: str, status: str, message: str) -> None:
    pass


def protocol_id_for(path: str) -> str:
    return "prt_" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


def _most_common(values):
    return Counter(values).most_common(1)[0][0] if values else None


async def ingest_file(path: str, nct_id: str | None = None, use_llm: bool = True,
                      progress: Progress = _noop) -> ProtocolGraph:
    if path.lower().endswith(".json"):
        graph = ProtocolGraph.model_validate_json(Path(path).read_text())
        if nct_id:
            graph.meta.nct_id = nct_id
        for step in ("ingest", "map_sections", "extract_soa", "extract_entities"):
            await progress(step, "done", "loaded from JSON")
        return graph

    doc = await asyncio.to_thread(read_pdf, path)
    parts = await asyncio.to_thread(split_sections, doc)
    await progress("ingest", "done", f"{doc.pages} pages, {len(parts)} sections")
    sections = await map_sections([s for s, _ in parts], use_llm=use_llm)
    parts = [(s, body) for s, (_, body) in zip(sections, parts, strict=True)]
    await progress("map_sections", "done", f"{sum(1 for s in sections if s.m11_id)} sections mapped to M11")

    lines = entities.body_lines(parts)
    numbers = entities.extract_numbers(lines)
    min_age, max_age = entities.age_limits(numbers, sections)
    meta = entities.extract_meta(doc, sections)
    meta.nct_id = nct_id or meta.nct_id
    meta.ratio = _most_common([str(n.value) for n in numbers if n.kind == "ratio"])

    soa = await asyncio.to_thread(extract_soa, path, doc)
    llm = {}
    if use_llm:
        from preflight.llm.client import LLMUnavailable

        if soa:
            context = "\n".join(ln.text for ln in entities.effective_parts(parts, ("1.1", "4.1")))
            try:
                soa = await fill_days_with_llm(soa, context)
            except LLMUnavailable as e:
                log.warning("SoA day normalization skipped: %s", e)
    soa_msg = f"{len(soa.visits)} visits, {len(soa.procedures)} procedures" if soa else "SoA table not found"
    await progress("extract_soa", "done", soa_msg)
    if use_llm:
        try:
            llm = await entities.extract_llm(parts)
        except LLMUnavailable as e:
            log.warning("LLM extraction skipped: %s", e)

    arms = llm.get("arms", [])
    n_arms = _most_common([int(n.value) for n in numbers if n.kind == "arms"])
    meta.n_arms = len(arms) or n_arms
    meta.condition = llm.get("condition")
    meta.sponsor = llm.get("sponsor")

    await progress("extract_entities", "done", f"{len(llm.get('objectives', []))} objectives, "
                   f"{len(llm.get('endpoints', []))} endpoints, {len(llm.get('criteria', []))} criteria, "
                   f"{len(numbers)} numbers")
    return ProtocolGraph(
        protocol_id=protocol_id_for(path),
        meta=meta,
        sections=sections,
        objectives=llm.get("objectives", []),
        endpoints=llm.get("endpoints", []),
        criteria=llm.get("criteria", []),
        min_age=min_age,
        max_age=max_age,
        arms=arms,
        soa=soa,
        stats=llm.get("stats") or Stats(sample_size=None, alpha=None, sided=None, power=None, effect_size=None,
                                        effect_type=None, control_rate=None, dropout=None, analyses=[]),
        numbers=numbers,
        xrefs=entities.extract_xrefs([ln for _, body in parts for ln in body]),
        abbreviations=entities.extract_abbreviations(doc, sections),
    )


SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "advisory": 3}
NEUTRAL_BURDEN = 50.0


class CheckResult(BaseModel):
    issues: list[Issue]
    score: Score
    completeness: Completeness
    verifier: dict | None = None


async def _registry_record(graph: ProtocolGraph) -> dict | None:
    if not graph.meta.nct_id:
        return None
    try:
        from preflight.ctgov.client import get_study

        return await get_study(graph.meta.nct_id)
    except Exception as e:  # B's client not merged yet, or network off
        log.warning("Registry record unavailable: %s", e)
        return None


def _burden_module():
    try:
        from preflight import burden

        return burden if hasattr(burden, "find_peers") else None
    except ImportError:
        return None


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen, out = set(), []
    for i in issues:
        key = (i.check_id, i.title.lower(), i.where.page)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


async def _ai_review(graph: ProtocolGraph, issues: list[Issue], completeness: Completeness, pdf_path: str | None,
                     progress: Progress) -> tuple[list[Issue], dict]:
    from preflight.reviewers.committee import review
    from preflight.reviewers.verifier import attach_fixes, verify

    thin = [f"{i.framework} {i.item_id} {i.title} ({i.status})" for i in completeness.items if i.status != "present"]
    findings = await review(graph, thin, [i.title for i in issues])
    await progress("reviewers", "done", f"{len(findings)} findings from the review committee")
    ai_issues, stats = await asyncio.to_thread(verify, findings, graph, pdf_path)
    ai_issues = attach_fixes(issues, ai_issues)
    await progress("verify", "done", f"{stats['dropped_ungrounded']} ungrounded findings dropped")
    return ai_issues, stats


async def check_graph(graph: ProtocolGraph, mode: str = "full", progress: Progress = _noop,
                      pdf_path: str | None = None) -> CheckResult:
    b = _burden_module()
    peers = await asyncio.to_thread(b.find_peers, graph) if b else None
    ctx = CheckContext(registry_record=await _registry_record(graph), peers=peers, settings={"mode": mode})
    issues = await asyncio.to_thread(run_checks, graph, ctx)
    await progress("rules", "done", f"{len(issues)} rule issues")
    completeness = compute_completeness(graph)

    verifier = None
    if mode == "full":
        ai_issues, verifier = await _ai_review(graph, issues, completeness, pdf_path, progress)
        issues += ai_issues
    else:
        await progress("reviewers", "skipped", "rules_only mode")
        await progress("verify", "skipped", "rules_only mode")

    if b:
        burden = float(b.burden_score(b.compute_burden(graph, peers)))
        await progress("burden", "done", f"burden score {burden:.0f}")
        hotspot_issues = b.hotspots(graph, peers) if peers else []
        await progress("peers", "done", f"{len(hotspot_issues)} hotspots")
    else:
        burden, hotspot_issues = NEUTRAL_BURDEN, []
        await progress("burden", "skipped", "burden module not available; neutral score")
        await progress("peers", "skipped", "peer module not available")

    issues = _dedupe(issues + hotspot_issues)
    if verifier:
        verifier["shown"] = sum(1 for i in issues if i.source.startswith("ai:"))
    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.where.page or 0))
    issues = [i.model_copy(update={"id": f"iss_{n:02d}"}) for n, i in enumerate(issues, 1)]
    s = completeness.summary
    result = CheckResult(issues=issues, score=score.compute(issues, s.present, s.thin, s.required, burden),
                         completeness=completeness, verifier=verifier)
    await progress("score", "done", f"score {result.score.overall}")
    return result


async def run_file(path: str, mode: str = "full", nct_id: str | None = None,
                   progress: Progress = _noop) -> CheckResult:
    graph = await ingest_file(path, nct_id=nct_id, use_llm=mode == "full", progress=progress)
    return await check_graph(graph, mode, progress=progress, pdf_path=path)
