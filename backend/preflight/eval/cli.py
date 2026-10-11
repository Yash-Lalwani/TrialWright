# ruff: noqa: E501
"""Benchmark commands: `preflight fetch | inject | bench`.

A owns preflight/cli.py. To expose these as top-level commands add two lines there:

    from preflight.eval.cli import register
    register(app)

Until then: `python -m preflight.eval.cli bench --set dev`.
"""
from __future__ import annotations

import asyncio
import json

import typer

from preflight.ctgov import client, corpus

from . import bench as bench_mod
from . import inject as inject_mod

app = typer.Typer(help="PreflightBench: corpus, error injection, scoring")


def _print_summary(res: dict) -> None:
    o, m = res["overall"], res["overall_measurable"]
    typer.echo(f"\n{res['set']} set, config={res['config']}, seeds={res['seeds']}, "
               f"{res['test_set']['protocols']} protocols, {res['test_set']['injected_errors']} injected errors")
    typer.echo(f"  all types       recall {o['recall']:.2f}  precision {o['precision']:.2f}  F1 {o['f1']:.2f}")
    typer.echo(f"  detectable types recall {m['recall']:.2f}  precision {m['precision']:.2f}  F1 {m['f1']:.2f}  (n={m['n_errors']})")
    typer.echo(f"  false alarms per clean protocol (critical+major): {res['false_alarms_per_clean_protocol']}")
    typer.echo("  by type:")
    for r in res["by_type"]:
        mark = "" if r["measurable"] else "  [needs LLM]"
        typer.echo(f"    {r['type']} {r['name'][:46]:46} {r['found']}/{r['n']}  recall {r['recall']:.2f}{mark}")


@app.command()
def fetch(split: str = typer.Option(None, help="dev or test; default all")) -> None:
    """Download every protocol PDF listed in data/corpus/manifest.csv."""
    paths = asyncio.run(corpus.fetch_corpus(split=split))
    typer.echo(f"{len(paths)} protocols present in {client.CORPUS_DIR}")


@app.command()
def inject(split: str = typer.Option("dev", "--set", help="dev or test"), seed: int = 1,
           all_: bool = typer.Option(False, "--all", help="every split")) -> None:
    """Plant errors into corpus PDFs; writes data/bench/{nct}_s{seed}.pdf and .json answer keys."""
    rows = [r for r in corpus.read_manifest() if all_ or r["split"] == split]
    for r in rows:
        reg = asyncio.run(client.get_study(r["nct_id"]))
        key = inject_mod.inject_file(str(client.CORPUS_DIR / f"{r['nct_id']}_protocol.pdf"), str(bench_mod.BENCH_DIR), seed,
                                     registry=reg)
        bad = inject_mod.verify_key(str(bench_mod.BENCH_DIR / key["injected_pdf"]), key,
                                    str(client.CORPUS_DIR / f"{r['nct_id']}_protocol.pdf"))
        typer.echo(f"{r['nct_id']}: {len(key['errors'])} errors injected, {len(key['skipped'])} skipped"
                   f"{'  PROBLEMS: ' + str(bad) if bad else ''}")


@app.command()
def bench(split: str = typer.Option("dev", "--set", help="dev or test"),
          config: str = typer.Option("rules_only", help="rules_only, full or llm_only (the N3 baseline)"),
          seeds: int = typer.Option(1, help="number of seeds (1..N)"),
          quick: bool = typer.Option(False, help="one seed; for CI"),
          refresh: bool = typer.Option(False, help="ignore cached pipeline runs"),
          allow_partial: bool = typer.Option(False, help="full config: accept runs that fell back to rules-only"),
          llm_graph: bool = typer.Option(True, help="use the LLM graph (cache or live) to plant T04/T05/T12; off = those types are skipped"),
          write: bool = typer.Option(True, help="write data/bench/results/*.json")) -> None:
    """Score the pipeline on injected errors (EVALUATION.md section 4)."""
    try:
        res = asyncio.run(bench_mod.bench(split, config, seeds=list(range(1, 2 if quick else seeds + 1)), refresh=refresh,
                                          allow_partial=allow_partial, use_llm_graph=llm_graph))
    except bench_mod.LLMUnavailable as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    _print_summary(res)
    if write:
        typer.echo(f"\nwrote {bench_mod.write_results(res)}")
    else:
        typer.echo(json.dumps(res["overall"]))


def register(parent: typer.Typer) -> None:
    for fn in (fetch, inject, bench):
        parent.command()(fn)


if __name__ == "__main__":
    app()
