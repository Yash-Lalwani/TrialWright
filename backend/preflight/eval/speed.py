# ruff: noqa: E501
"""N10: wall-clock time and LLM cost per protocol for the full pipeline, measured LIVE (LLM_MODE=live ignores the response cache).

Replayed benchmark runs finish in seconds because every model answer comes from disk, so their timings say nothing about a
real user's wait. This module runs the full pipeline for real on each clean protocol of a split and sums the provider-reported
cost (LLMCall rows). Result: data/bench/results/speed_{split}.json, which `bench` folds into speed_cost.
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import time

from sqlmodel import select

from preflight.ctgov import client
from preflight.ctgov.corpus import read_manifest

from .bench import RESULTS_DIR


async def measure(split: str) -> dict:
    from preflight.db import LLMCall, init_db, session
    from preflight.llm.client import current_run_id
    from preflight.pipeline import check_graph, ingest_file

    init_db()
    rows = []
    for r in (r for r in read_manifest(client.CORPUS_DIR / "manifest.csv") if r["split"] == split):
        nct = r["nct_id"]
        pdf = str(client.CORPUS_DIR / f"{nct}_protocol.pdf")
        rid = f"speed_{nct}_{int(time.time())}"
        token = current_run_id.set(rid)
        t0 = time.monotonic()
        try:
            graph = await ingest_file(pdf, nct_id=nct, use_llm=True)
            await check_graph(graph, "full", pdf_path=pdf)
        finally:
            current_run_id.reset(token)
        secs = time.monotonic() - t0
        with session() as s:
            calls = s.exec(select(LLMCall).where(LLMCall.run_id == rid)).all()
        rows.append({"nct_id": nct, "seconds": round(secs, 1), "usd": round(sum(c.cost_usd for c in calls), 4), "llm_calls": len(calls),
                     "cache_hits": sum(c.cache_hit for c in calls), "tokens_in": sum(c.tokens_in for c in calls), "tokens_out": sum(c.tokens_out for c in calls)})
    out = {"set": split, "mode": os.getenv("LLM_MODE"), "median_seconds": statistics.median(r["seconds"] for r in rows),
           "median_usd": statistics.median(r["usd"] for r in rows), "per_protocol": rows}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"speed_{split}.json").write_text(json.dumps(out, indent=1))
    return out


def load(split: str) -> dict | None:
    p = RESULTS_DIR / f"speed_{split}.json"
    return json.loads(p.read_text()) if p.exists() else None


if __name__ == "__main__":
    import sys

    print(json.dumps(asyncio.run(measure(sys.argv[1] if len(sys.argv) > 1 else "dev")), indent=1))
