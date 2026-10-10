# ruff: noqa: E501
"""PreflightBench runner: clean run + injected run per protocol, scored with the matching rule.

    preflight bench --set dev|test [--config rules_only|full] [--seeds 1] [--quick]

Output follows CONTRACTS.md 4.12 (fields not measured yet are null) plus honesty fields: which error types the
configuration can even see (`measurable`), and recall over those.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from preflight.ctgov import client
from preflight.ctgov.corpus import read_manifest

from . import inject, metrics
from .types import TYPES

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = Path(os.environ.get("PREFLIGHT_BENCH_DIR", ROOT / "data" / "bench"))
RESULTS_DIR = BENCH_DIR / "results"
CONFIGS = ("rules_only", "full")

# (path, config, nct_id) -> (issues as dicts, seconds, llm_cost_usd[, facts]); facts = what ingest extracted
Runner = Callable[[str, str, str], Awaitable[tuple]]


class LLMUnavailable(RuntimeError):
    pass


def require_llm_for(config: str) -> None:
    """A 'full' run without an LLM key or recorded responses would silently degrade to rules-only. Refuse instead."""
    if config != "full":
        return
    cache = ROOT / "data" / "llm_cache"
    has_cache = cache.exists() and any(p for p in cache.iterdir() if p.name != ".gitkeep")
    if not (os.environ.get("OPENROUTER_API_KEY") or has_cache):
        raise LLMUnavailable("config 'full' needs OPENROUTER_API_KEY (live/record) or a populated data/llm_cache "
                             "(replay). Without either the pipeline would silently run rules-only.")


def facts_digest(graph) -> dict:
    """Compact record of what ingest extracted, so a miss can be classed 'not extracted' vs 'extracted, not flagged'."""
    soa = graph.soa
    return {
        "numbers": [[n.kind, n.span.page, str(n.value)] for n in graph.numbers],
        "xrefs": [[x["span"]["page"], x["target"]] for x in graph.xrefs],
        "windows": [[v.name, v.study_day, v.window_minus, v.window_plus] for v in (soa.visits if soa else [])],
        "counts": {"objectives": len(graph.objectives), "endpoints": len(graph.endpoints), "criteria": len(graph.criteria),
                   "sections": len(graph.sections), "soa_visits": len(soa.visits) if soa else 0},
    }


async def default_runner(path: str, config: str, nct_id: str) -> tuple:
    from preflight.pipeline import check_graph, ingest_file

    t0 = time.monotonic()
    graph = await ingest_file(path, nct_id=nct_id, use_llm=config == "full")
    res = await check_graph(graph, config, pdf_path=path)
    return [i.model_dump() for i in res.issues], time.monotonic() - t0, 0.0, facts_digest(graph)


async def cached_run(runner: Runner, path: str, config: str, nct_id: str, refresh: bool = False) -> dict:
    """Run once per (file content, config); store under results/runs so reruns and CI are cheap."""
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    cp = RESULTS_DIR / "runs" / f"{Path(path).stem}_{config}_{digest}.json"
    if cp.exists() and not refresh:
        return json.loads(cp.read_text())
    res = await runner(path, config, nct_id)
    out = {"issues": res[0], "seconds": round(res[1], 2), "llm_cost_usd": round(res[2], 4),
           "facts": res[3] if len(res) > 3 else None}
    if config == "full" and extracted_with_llm(out) is not True:
        return out  # never cache a degraded 'full' run: adding an API key later must not reuse it
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(out))
    return out


def extracted_with_llm(run: dict) -> bool | None:
    """Did the LLM extraction step actually run? (objectives/endpoints/criteria exist only if it did.) None = unknown."""
    c = (run.get("facts") or {}).get("counts")
    return None if c is None else bool(c["objectives"] + c["endpoints"] + c["criteria"])


async def bench(split: str, config: str = "rules_only", seeds: list[int] | None = None, runner: Runner | None = None,
                refresh: bool = False, corpus_dir: Path | None = None, only: list[str] | None = None,
                allow_partial: bool = False) -> dict:
    require_llm_for(config) if runner is None else None
    runner = runner or default_runner
    seeds = seeds or [1]
    corpus = corpus_dir or client.CORPUS_DIR
    rows = [r for r in read_manifest(corpus / "manifest.csv") if r["split"] == split and (not only or r["nct_id"] in only)]
    scored, per_protocol, clean_runs, secs, costs, llm_ok = [], [], [], [], [], []
    for row in rows:
        nct = row["nct_id"]
        pdf = corpus / f"{nct}_protocol.pdf"
        if not pdf.exists():
            raise FileNotFoundError(f"{pdf} missing; run fetch_corpus first")
        clean = await cached_run(runner, str(pdf), config, nct, refresh)
        clean_runs.append(clean["issues"])
        llm_ok.append(extracted_with_llm(clean))
        secs.append(clean["seconds"])
        costs.append(clean["llm_cost_usd"])
        try:
            registry = await client.get_study(nct)
        except Exception:  # offline and not cached: T18 is skipped and says so
            registry = None
        for seed in seeds:
            key = inject.inject_file(str(pdf), str(BENCH_DIR), seed, registry=registry)
            bad = inject.verify_key(str(BENCH_DIR / key["injected_pdf"]), key)
            if bad:
                raise RuntimeError(f"injection did not land as recorded: {bad}")
            run = await cached_run(runner, str(BENCH_DIR / key["injected_pdf"]), config, nct, refresh)
            llm_ok.append(extracted_with_llm(run))
            s = metrics.score_run(key["errors"], run["issues"], clean["issues"], run.get("facts"))
            scored.append(s)
            secs.append(run["seconds"])
            costs.append(run["llm_cost_usd"])
            per_protocol.append({"nct_id": nct, "seed": seed, "injected": len(key["errors"]), "tp": len(s.tp),
                                 "fn": len(s.fn), "fp": len(s.fp), "skipped": key["skipped"],
                                 "missed": [{"type": e["type"], "description": e["description"], "page": e["page"],
                                             "line": e.get("new_line"), "why": s.diagnosis.get(e["error_id"])}
                                            for e in s.fn]})
    if config == "full":
        n_ok = sum(1 for x in llm_ok if x)
        if n_ok < len(llm_ok) and not allow_partial:
            raise LLMUnavailable(f"config 'full' but only {n_ok} of {len(llm_ok)} runs produced LLM extraction (cache misses or "
                                 "no key): those runs silently fell back to rules-only. Set OPENROUTER_API_KEY with LLM_MODE=record "
                                 "to record them, or pass --allow-partial to accept a mixed result.")
    agg = metrics.aggregate(scored)
    measurable = {t for t, spec in TYPES.items() if config == "full" or not spec.needs_llm}
    for r in agg["by_type"]:
        r["measurable"] = r["type"] in measurable
    m_tp = sum(1 for s in scored for e, _ in s.tp if e["type"] in measurable)
    m_fn = sum(1 for s in scored for e in s.fn if e["type"] in measurable)
    m_fp = sum(len(s.fp) for s in scored)
    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "set": split, "config": config, "seeds": seeds,
        "llm_enabled": config == "full",
        "llm_extraction": {"runs": len(llm_ok), "with_extraction": sum(1 for x in llm_ok if x)},
        "test_set": {"protocols": len(rows), **agg["test_set"]},
        "overall": agg["overall"],
        "overall_measurable": {**metrics.prf(m_tp, m_fp, m_fn), "n_errors": m_tp + m_fn,
                               "note": "only error types this config can detect (rules_only cannot see types that need LLM extraction)"},
        "by_type": agg["by_type"], "by_category": agg["by_category"],
        "false_alarms_per_clean_protocol": metrics.false_alarms_per_clean(clean_runs),
        "clean_flags_by_check": metrics.clean_flags_by_check(clean_runs),
        "per_protocol": per_protocol,
        "speed_cost": {"median_seconds": round(sorted(secs)[len(secs) // 2], 2) if secs else None,
                       "median_usd": round(sorted(costs)[len(costs) // 2], 4) if costs else None},
        "ablation": None, "hallucination": None, "human_baseline": None, "real_findings": None,
        "soa_extraction": None, "case_studies": None,
    }


def write_results(result: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = result["generated_at"].replace(":", "").replace("-", "")
    path = RESULTS_DIR / f"{result['set']}_{result['config']}_{stamp}.json"
    path.write_text(json.dumps(result, indent=1))
    return path
