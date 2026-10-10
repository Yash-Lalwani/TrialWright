import hashlib
import logging
from collections import Counter
from pathlib import Path

from preflight.graph.models import ProtocolGraph, Stats
from preflight.ingest import entities
from preflight.ingest.m11_map import map_sections
from preflight.ingest.pdf import read_pdf
from preflight.ingest.sections import split_sections

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

    llm = {}
    if use_llm:
        from preflight.llm.client import LLMCacheMiss

        try:
            llm = await entities.extract_llm(parts)
        except LLMCacheMiss as e:
            log.warning("LLM extraction skipped: %s", e)

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
        soa=None,
        stats=llm.get("stats") or Stats(sample_size=None, alpha=None, sided=None, power=None, effect_size=None,
                                        effect_type=None, control_rate=None, dropout=None, analyses=[]),
        numbers=numbers,
        xrefs=entities.extract_xrefs(lines),
        abbreviations=entities.extract_abbreviations(doc, sections),
    )
