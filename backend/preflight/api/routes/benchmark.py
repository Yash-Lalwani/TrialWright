"""CONTRACTS 4.12: serve the latest benchmark results (data/bench/results/*.json, written by `preflight bench`).

Headline file: prefer the test set over dev, and the full config over the others; newest wins a tie. The response is
the results file in the CONTRACTS shape plus additive fields `set` and `config` so the UI can say which split a number
comes from (dev numbers were tuned on and must be labelled). `ablation` lists the newest result of each config on the
same split. Nothing is invented: a section with no data is null.
"""
import json

from fastapi import APIRouter, HTTPException

from preflight.eval.bench import RESULTS_DIR
from preflight.llm import client as llm

router = APIRouter(prefix="/api")

NULLABLE = ("hallucination", "human_baseline", "real_findings", "soa_extraction", "speed_cost", "case_studies")


def _load() -> list[dict]:
    out = []
    for p in sorted(RESULTS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and {"set", "config", "overall"} <= set(d):
            out.append(d)
    return out


def headline(results: list[dict]) -> dict | None:
    rank = lambda d: (d["set"] == "test", d["config"] == "full", d["generated_at"])  # noqa: E731
    return max(results, key=rank, default=None)


def shape(results: list[dict]) -> dict | None:
    top = headline(results)
    if top is None:
        return None
    latest: dict[str, dict] = {}
    for d in sorted((d for d in results if d["set"] == top["set"]), key=lambda d: d["generated_at"]):
        latest[d["config"]] = d
    order = ("rules_only", "llm_only", "full")
    ablation = [{"config": c, **{k: latest[c]["overall"][k] for k in ("recall", "precision", "f1")}} for c in order if c in latest]
    body = {"generated_at": top["generated_at"], "model": llm.model() if top.get("llm_enabled") else None,
            "set": top["set"], "config": top["config"], "test_set": top["test_set"], "overall": top["overall"],
            "by_type": top["by_type"], "by_category": top["by_category"], "ablation": ablation,
            "false_alarms_per_clean_protocol": top.get("false_alarms_per_clean_protocol")}
    body.update({k: top.get(k) for k in NULLABLE})
    return body


@router.get("/benchmark")
def get_benchmark():
    body = shape(_load())
    if body is None:
        raise HTTPException(404, "No benchmark results yet; run `preflight bench --set test --config full`")
    return body
