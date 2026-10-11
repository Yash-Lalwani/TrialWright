# ruff: noqa: E501
"""N3 baseline: an LLM with one generic "find all problems" prompt per chunk of the protocol, no rules, no schedule parsing,
no verifier. This is what a user would get by pasting the protocol into a chat model.

Fairness choices (all in the model's favour or neutral):
  * the same model and the same injected PDFs as the other configs;
  * chunks of CHUNK_PAGES pages, so a very long protocol still fits; the price is that it cannot see an inconsistency whose
    two halves sit in different chunks (this is a real limit of the approach, not an artefact);
  * scoring is check-agnostic: a finding counts if it points at the injected location (page or quote), whatever it calls the problem.
Each finding is also tested for grounding: is its quote actually on the page it cites? That feeds the hallucination numbers.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Literal

import pymupdf
from pydantic import BaseModel
from rapidfuzz import fuzz


CHUNK_PAGES = 12
CONCURRENCY = 4

SYSTEM = ("You are a meticulous reviewer of clinical trial protocols. Find every error in the excerpt you are given: "
          "numbers or facts that contradict each other, impossible or inconsistent values (ages, doses, dates, windows, "
          "sample size, randomisation ratio), cross-references to sections that do not exist, missing information a protocol must contain, "
          "criteria that contradict each other, endpoints with no analysis. Report only problems you can point to. "
          "For each, give the page number shown in the excerpt and a short VERBATIM quote from that page. Report at most 12 findings, most serious first; if there is nothing wrong return an empty list.")


class _Finding(BaseModel):
    title: str
    page: int
    quote: str
    severity: Literal["critical", "major", "minor"]


class _Findings(BaseModel):
    findings: list[_Finding]


def page_texts(path: str) -> dict[int, str]:
    """Raw text of every page as a user would paste it, INCLUDING tables (A's read_pdf drops table cells from its line list)."""
    with pymupdf.open(path) as doc:
        return {n: page.get_text("text") for n, page in enumerate(doc, 1)}


def chunks(pages_text: dict[int, str], size: int = CHUNK_PAGES) -> list[tuple[str, dict[int, str]]]:
    """(prompt text, {page: page text}) per chunk of `size` pages."""
    pages = sorted(pages_text)
    out = []
    for i in range(0, len(pages), size):
        part = {p: pages_text[p] for p in pages[i:i + size]}
        out.append(("\n\n".join(f"[page {p}]\n{t}" for p, t in part.items()), part))
    return out


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


FUZZY = 90


def grounded(quote: str, page_text: str) -> bool:
    """The quote is on the cited page. Exact after normalising whitespace and punctuation, or a near match (>= FUZZY) so that a
    table row name with its footnote letter ('Pharmacokinetic Samplingn') or a hyphenated line break is not called invented.
    An invented sentence does not reach 90 against a page that never says it."""
    q, t = _norm(quote), _norm(page_text)
    if not q or not t:
        return False
    return q in t or fuzz.partial_ratio(q, t) >= FUZZY


async def run_llm_only(path: str, config: str = "llm_only", nct_id: str = "") -> tuple:
    """Same return shape as bench.default_runner: (issues, seconds, cost, facts)."""
    from preflight.llm.client import LLMUnavailable, complete_json

    t0 = time.monotonic()
    texts = await asyncio.to_thread(page_texts, path)
    sem = asyncio.Semaphore(CONCURRENCY)

    failed = 0

    async def one(text: str, part: dict[int, str]) -> list[dict]:
        nonlocal failed
        async with sem:
            for attempt in range(2):     # one retry; a chunk that still fails is counted and reported, never hidden
                try:
                    out = await complete_json("llm_only", SYSTEM, text, _Findings)
                    break
                except LLMUnavailable:
                    if attempt == 1:
                        failed += 1
                        return []
        return [{"id": "", "check_id": "LLM", "source": "ai:llm_only", "category": "consistency", "severity": f.severity, "title": f.title,
                 "where": {"section": None, "page": f.page, "bbox": None, "quote": f.quote}, "related": [],
                 "why": {"explanation": f.title, "standard_ref": None, "amendment_category": "clerical"}, "fix": None,
                 "confidence": 0.5, "verified": False, "status": "open", "grounded": grounded(f.quote, part.get(f.page, ""))} for f in out.findings]

    results = await asyncio.gather(*(one(t, p) for t, p in chunks(texts)))
    issues = [i for r in results for i in r]
    return issues, time.monotonic() - t0, 0.0, {"counts": {"objectives": 1, "endpoints": 0, "criteria": 0, "sections": 0, "soa_visits": 0}, "chunks": len(results), "chunks_failed": failed}


def hallucination(runs: list[tuple[str, dict]]) -> dict:
    """N4 for one config: AI findings produced, dropped by the verifier (full only) and shown but not grounded.
    A shown finding is grounded if its quote is on the page it cites (checked here, independently of the verifier).
    runs: (pdf path, run dict with issues and optional facts.verifier)."""
    produced = dropped = shown = ungrounded = 0
    for path, run in runs:
        ai = [i for i in run["issues"] if str(i.get("source", "")).startswith("ai:")]
        if not ai:
            dropped += ((run.get("facts") or {}).get("verifier") or {}).get("dropped_ungrounded", 0)
            produced += ((run.get("facts") or {}).get("verifier") or {}).get("dropped_ungrounded", 0)
            continue
        text = page_texts(path)
        v = (run.get("facts") or {}).get("verifier") or {}
        dropped += v.get("dropped_ungrounded", 0)
        produced += len(ai) + v.get("dropped_ungrounded", 0)
        shown += len(ai)
        ungrounded += sum(1 for i in ai if not grounded((i.get("where") or {}).get("quote") or "", text.get((i.get("where") or {}).get("page"), "")))
    return {"ai_findings": produced, "dropped_ungrounded": dropped, "shown": shown, "shown_ungrounded": ungrounded}
