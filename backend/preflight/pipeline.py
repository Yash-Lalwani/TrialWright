import hashlib
import logging
from collections import Counter
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


def protocol_id_for(path: str) -> str:
    return "prt_" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


def _most_common(values):
    return Counter(values).most_common(1)[0][0] if values else None


async def ingest_file(path: str, nct_id: str | None = None, use_llm: bool = True) -> ProtocolGraph:
    if path.lower().endswith(".json"):
        graph = ProtocolGraph.model_validate_json(Path(path).read_text())
        if nct_id:
            graph.meta.nct_id = nct_id
        return graph

    doc = read_pdf(path)
    parts = split_sections(doc)
    sections = await map_sections([s for s, _ in parts], use_llm=use_llm)
    parts = [(s, body) for s, (_, body) in zip(sections, parts, strict=True)]

    lines = entities.body_lines(parts)
    numbers = entities.extract_numbers(lines)
    min_age, max_age = entities.age_limits(numbers, sections)
    meta = entities.extract_meta(doc, sections)
    meta.nct_id = nct_id or meta.nct_id
    meta.ratio = _most_common([str(n.value) for n in numbers if n.kind == "ratio"])

    soa = extract_soa(path, doc)
    llm = {}
    if use_llm:
        from preflight.llm.client import LLMCacheMiss

        try:
            llm = await entities.extract_llm(parts)
        except LLMCacheMiss as e:
            log.warning("LLM extraction skipped: %s", e)
        if soa:
            context = "\n".join(ln.text for ln in entities.effective_parts(parts, ("1.1", "4.1")))
            try:
                soa = await fill_days_with_llm(soa, context)
            except LLMCacheMiss as e:
                log.warning("SoA day normalization skipped: %s", e)

    arms = llm.get("arms", [])
    n_arms = _most_common([int(n.value) for n in numbers if n.kind == "arms"])
    meta.n_arms = len(arms) or n_arms
    meta.condition = llm.get("condition")
    meta.sponsor = llm.get("sponsor")

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
        xrefs=entities.extract_xrefs(lines),
        abbreviations=entities.extract_abbreviations(doc, sections),
    )


SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "advisory": 3}
NEUTRAL_BURDEN = 50.0


class CheckResult(BaseModel):
    issues: list[Issue]
    score: Score
    completeness: Completeness


async def _registry_record(graph: ProtocolGraph) -> dict | None:
    if not graph.meta.nct_id:
        return None
    try:
        from preflight.ctgov.client import get_study

        return await get_study(graph.meta.nct_id)
    except Exception as e:  # B's client not merged yet, or network off
        log.warning("Registry record unavailable: %s", e)
        return None


def _burden(graph: ProtocolGraph) -> tuple[object | None, list[Issue], float]:
    """B's peers, hotspots and burden score; neutral values until B's module lands."""
    try:
        from preflight.burden import burden_score, compute_burden, find_peers, hotspots
    except ImportError:
        log.warning("Burden module not available; using neutral burden score")
        return None, [], NEUTRAL_BURDEN
    peers = find_peers(graph)
    report = compute_burden(graph, peers)
    return peers, hotspots(graph, peers) if peers else [], float(burden_score(report))


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen, out = set(), []
    for i in issues:
        key = (i.check_id, i.title.lower(), i.where.page)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


async def check_graph(graph: ProtocolGraph, mode: str = "full") -> CheckResult:
    peers, hotspot_issues, burden = _burden(graph)
    ctx = CheckContext(registry_record=await _registry_record(graph), peers=peers, settings={"mode": mode})
    issues = _dedupe(run_checks(graph, ctx) + hotspot_issues)
    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.where.page or 0))
    issues = [i.model_copy(update={"id": f"iss_{n:02d}"}) for n, i in enumerate(issues, 1)]
    completeness = compute_completeness(graph)
    s = completeness.summary
    return CheckResult(issues=issues, score=score.compute(issues, s.present, s.thin, s.required, burden),
                       completeness=completeness)


async def run_file(path: str, mode: str = "full", nct_id: str | None = None) -> CheckResult:
    graph = await ingest_file(path, nct_id=nct_id, use_llm=mode == "full")
    return await check_graph(graph, mode)
