# ruff: noqa: E501
import asyncio
import csv
import json
import shutil
from pathlib import Path

import pymupdf
import pytest

from preflight.eval import bench, inject
from tests.test_eval_inject import BODY

BASE = ["T06", "T08", "T10", "T14"]


def corpus(tmp_path: Path) -> Path:
    d = tmp_path / "corpus"
    d.mkdir()
    doc = pymupdf.open()
    page = doc.new_page()
    for n, line in enumerate(BODY):
        page.insert_text((72, 90 + 22 * n), line, fontname="tiro", fontsize=11)
    doc.save(d / "NCT00000001_protocol.pdf")
    with open(d / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["nct_id", "split"])
        w.writeheader()
        w.writerow({"nct_id": "NCT00000001", "split": "dev"})
    return d


def key_for(path: str) -> dict:
    """Answer key of the injected file, found via its sibling .json."""
    return json.loads(Path(path).with_suffix(".json").read_text())


async def perfect_runner(path, config, nct):
    """Pretend pipeline: flags exactly what was injected (one clean-run issue is shared)."""
    k = key_for(path) if "_s" in Path(path).stem else {"errors": []}
    titles = {"T06": "Minimum age disagrees", "T08": "Sample size disagrees", "T10": "Randomization ratio disagrees", "T07": "Dose disagrees across sections",
              "T14": "Cross-reference to Section 99.3.2, which does not exist"}
    issues = [{"check_id": e["expected_checks"][0], "title": titles.get(e["type"], f"flag {e['type']}"), "severity": "major",
               "where": {"page": e["page"], "quote": None}, "related": []} for e in k["errors"]]
    issues.append({"check_id": "B1", "title": "pre-existing real issue", "severity": "major",
                   "where": {"page": None, "quote": None}, "related": []})
    return issues, 1.0, 0.0


async def empty_runner(path, config, nct):
    return [], 1.0, 0.0


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "BENCH_DIR", tmp_path / "bench")
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path / "bench" / "results")
    monkeypatch.setattr(inject, "_sections", lambda pdf: [])
    return corpus(tmp_path)


def test_perfect_detector_scores_full_recall_and_ignores_preexisting(env):
    res = asyncio.run(bench.bench("dev", "rules_only", runner=perfect_runner, corpus_dir=env))
    assert res["overall"]["recall"] == 1.0 and res["overall"]["precision"] == 1.0
    assert res["false_alarms_per_clean_protocol"] == 1.0  # shared pre-existing issue


def test_empty_detector_scores_zero_recall(env):
    res = asyncio.run(bench.bench("dev", "rules_only", runner=empty_runner, corpus_dir=env))
    assert res["overall"]["recall"] == 0.0 and res["test_set"]["injected_errors"] > 0
    assert res["per_protocol"][0]["missed"]


def test_rules_only_marks_llm_dependent_types_unmeasurable(env):
    res = asyncio.run(bench.bench("dev", "rules_only", runner=empty_runner, corpus_dir=env))
    flags = {r["type"]: r["measurable"] for r in res["by_type"]}
    assert flags and all(flags[t] == (not bench.TYPES[t].needs_llm) for t in flags)


def test_full_config_refuses_without_llm_key_or_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(bench, "ROOT", tmp_path)  # empty data/llm_cache
    with pytest.raises(bench.LLMUnavailable):
        bench.require_llm_for("full")
    bench.require_llm_for("rules_only")  # fine


def test_results_written_and_runs_cached(env):
    calls = []

    async def counting(path, config, nct):
        calls.append(path)
        return await empty_runner(path, config, nct)

    asyncio.run(bench.bench("dev", "rules_only", runner=counting, corpus_dir=env))
    n = len(calls)
    asyncio.run(bench.bench("dev", "rules_only", runner=counting, corpus_dir=env))
    assert len(calls) == n  # second pass served from cache
    path = bench.write_results(asyncio.run(bench.bench("dev", "rules_only", runner=empty_runner, corpus_dir=env)))
    assert json.loads(path.read_text())["config"] == "rules_only"
    shutil.rmtree(env)


def _runner_with_counts(n_endpoints):
    async def run(path, config, nct):
        return [], 1.0, 0.0, {"numbers": [], "xrefs": [], "windows": [], "counts": {"objectives": n_endpoints,
                                                                                    "endpoints": n_endpoints, "criteria": 0}}
    return run


def test_full_config_rejects_runs_that_silently_fell_back_to_rules_only(env, monkeypatch):
    monkeypatch.setattr(bench, "require_llm_for", lambda c: None)
    import pytest as _p
    with _p.raises(bench.LLMUnavailable, match="silently fell back"):
        asyncio.run(bench.bench("dev", "full", runner=_runner_with_counts(0), corpus_dir=env))
    ok = asyncio.run(bench.bench("dev", "full", runner=_runner_with_counts(2), corpus_dir=env))
    assert ok["llm_extraction"]["runs"] == ok["llm_extraction"]["with_extraction"] > 0
    part = asyncio.run(bench.bench("dev", "full", runner=_runner_with_counts(0), corpus_dir=env, allow_partial=True, refresh=True))
    assert part["llm_extraction"]["with_extraction"] == 0
