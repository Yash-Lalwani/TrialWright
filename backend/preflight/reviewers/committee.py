import asyncio
import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from preflight.graph.models import ProtocolGraph, Section

log = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"
ROLES = ["medical_writer", "clinical_scientist", "biostatistician", "clinical_ops"]
MAX_CHARS = 12000
RULES = (
    "Return at most 8 findings. Each finding must quote text copied verbatim from the input (one sentence or "
    "phrase under 200 characters) and give the page number shown in the [pN] marker before that text. "
    "Only report problems you can point to in the text."
)


class Finding(BaseModel):
    title: str
    quote: str
    page: int
    section: str | None = None
    category: Literal["completeness", "consistency", "burden", "amendment_risk", "advisory"]
    severity: Literal["critical", "major", "minor", "advisory"]
    explanation: str
    fix: str


class ReviewerOut(BaseModel):
    findings: list[Finding]


def _section_text(sections: list[Section], prefixes: tuple[str, ...], limit: int) -> str:
    out = []
    for s in sections:
        m11 = s.m11_id or ""
        if any(m11 == p or m11.startswith(p + ".") for p in prefixes):
            out.append(f"## {s.title}\n[p{s.page_start}] {s.text}")
    return "\n\n".join(out)[:limit]


def _soa_table(graph: ProtocolGraph) -> str:
    if not graph.soa:
        return "No Schedule of Activities was extracted."
    soa = graph.soa
    head = " | ".join(f"{v.name} (Day {v.study_day:g})" if v.study_day is not None else v.name for v in soa.visits)
    rows = [f"Procedure | {head}"]
    for p in soa.procedures:
        rows.append(f"{p.name} | " + " | ".join("X" if soa.cells.get(v.id, {}).get(p.id) else "" for v in soa.visits))
    page = soa.span.page if soa.span else "?"
    return f"[p{page}] Schedule of Activities\n" + "\n".join(rows)


def slices(graph: ProtocolGraph, thin: list[str], rule_titles: list[str]) -> dict[str, str]:
    """The part of the protocol each reviewer sees."""
    s = graph.sections
    facts = json.dumps({"objectives": [o.model_dump(exclude={"span"}) for o in graph.objectives],
                        "endpoints": [e.model_dump(exclude={"span"}) for e in graph.endpoints],
                        "stats": graph.stats.model_dump(exclude={"analyses"})}, default=str)[:3000]
    return {
        "medical_writer": f"Thin or missing sections: {', '.join(thin) or 'none'}\n\n"
                          + _section_text(s, ("1.1", "4.1", "3"), MAX_CHARS),
        "clinical_scientist": _section_text(s, ("5.1", "5.2", "5.3", "3", "8.4", "9"), MAX_CHARS),
        "biostatistician": f"Extracted facts: {facts}\n\n" + _section_text(s, ("3", "10"), MAX_CHARS - 3000),
        "clinical_ops": _soa_table(graph)[:6000] + "\n\nRule findings already raised:\n" + "\n".join(rule_titles[:20])
                        + "\n\n" + _section_text(s, ("8",), MAX_CHARS - 7000),
    }


async def review(graph: ProtocolGraph, thin: list[str], rule_titles: list[str]) -> list[tuple[str, Finding]]:
    """Run the four reviewers in parallel; a reviewer that fails (e.g. replay cache miss) is skipped."""
    from preflight.llm.client import complete_json

    inputs = slices(graph, thin, rule_titles)

    async def one(role: str):
        system = f"{(PROMPTS / f'{role}.txt').read_text().strip()}\n\n{RULES}"
        out = await complete_json(f"reviewer:{role}", system, inputs[role], ReviewerOut)
        return [(role, f) for f in out.findings]

    results = await asyncio.gather(*(one(r) for r in ROLES if inputs[r].strip()), return_exceptions=True)
    findings = []
    for r in results:
        if isinstance(r, Exception):
            log.warning("Reviewer skipped: %s", r)
        else:
            findings.extend(r)
    return findings
