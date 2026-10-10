import typer
import uvicorn

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    uvicorn.run("preflight.api.main:app", host=host, port=port, reload=reload)


@app.command()
def check(
    path: str,
    nct_id: str = typer.Option(None, help="ClinicalTrials.gov id, if known"),
    dump_graph: bool = typer.Option(False, "--dump-graph", help="Print the Protocol Graph as JSON"),
    rules_only: bool = typer.Option(False, "--rules-only", help="No LLM calls"),
):
    import asyncio
    import time

    from preflight.pipeline import check_graph, ingest_file

    async def run():
        graph = await ingest_file(path, nct_id=nct_id, use_llm=not rules_only)
        if dump_graph:
            return graph, None
        return graph, await check_graph(graph, "rules_only" if rules_only else "full", pdf_path=path)

    start = time.monotonic()
    graph, result = asyncio.run(run())
    if dump_graph:
        typer.echo(graph.model_dump_json(indent=2))
        return
    m = graph.meta
    typer.echo(f"{graph.protocol_id}  {m.title[:90]}")
    typer.echo(f"  phase={m.phase} masking={m.masking} allocation={m.allocation} ratio={m.ratio} "
               f"arms={m.n_arms} ages={graph.min_age}-{graph.max_age} nct={m.nct_id}")
    mapped = sum(1 for s in graph.sections if s.m11_id)
    typer.echo(f"  sections={len(graph.sections)} (m11 mapped {mapped}) numbers={len(graph.numbers)} "
               f"xrefs={len(graph.xrefs)} abbreviations defined={len(graph.abbreviations['defined'])}")
    typer.echo(f"  objectives={len(graph.objectives)} endpoints={len(graph.endpoints)} criteria={len(graph.criteria)} "
               f"arms={len(graph.arms)} sample_size={graph.stats.sample_size}")
    if graph.soa:
        dated = sum(v.study_day is not None for v in graph.soa.visits)
        typer.echo(f"  soa: p{graph.soa.span.page} visits={len(graph.soa.visits)} ({dated} with study day) "
                   f"procedures={len(graph.soa.procedures)}")
    sc, cs = result.score, result.completeness.summary
    typer.echo(f"  score={sc.overall} (completeness {sc.completeness}, consistency {sc.consistency}, "
               f"burden {sc.burden}, amendment risk {sc.amendment_risk})  "
               f"M11/SPIRIT present={cs.present} thin={cs.thin} missing={cs.missing}")
    typer.echo(f"\n{len(result.issues)} issues")
    for i in result.issues:
        typer.echo(f"  {i.id} [{i.severity:8}] {i.check_id:3} p{i.where.page or '-':<4} {i.title[:95]}")
        if i.where.quote:
            typer.echo(f"        \"{i.where.quote[:100]}\"")
    typer.echo(f"\n{time.monotonic() - start:.1f}s")


@app.command("mock-issues")
def mock_issues(pdf: str, out: str = "../frontend/mocks/issues_real.json"):
    """Write contract-shaped issues with real pages and bboxes for a PDF."""
    import json
    from pathlib import Path

    from preflight.ingest.mock_issues import build

    data = build(pdf)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, indent=2) + "\n")
    for i in data["items"]:
        typer.echo(f'{i["id"]} {i["check_id"]} p{i["where"]["page"]} {i["where"]["bbox"]} {i["where"]["quote"][:60]}')
    typer.echo(f"wrote {data['total']} issues to {out}")


@app.command("llm-probe")
def llm_probe():
    """Check whether the model honours response_format json_schema on OpenRouter."""
    import asyncio
    import json

    from pydantic import BaseModel, ValidationError

    from preflight.llm.client import _get_client, model

    class Probe(BaseModel):
        visit: str
        study_week: float
        procedures: list[str]

    user = "Week 24 visit: tumor imaging (CT/MRI), hematology, ECOG. Extract visit, study_week, procedures."
    formats = {
        "json_schema": {"type": "json_schema",
                        "json_schema": {"name": "Probe", "schema": Probe.model_json_schema(), "strict": True}},
        "json_object": {"type": "json_object"},
    }

    async def run():
        for name, fmt in formats.items():
            try:
                resp = await _get_client().chat.completions.create(
                    model=model(), temperature=0, response_format=fmt,
                    messages=[{"role": "system", "content": "Return JSON only."},
                              {"role": "user", "content": user}],
                    extra_body={"provider": {"data_collection": "deny", "require_parameters": True}},
                )
                content = resp.choices[0].message.content
                Probe.model_validate_json(content)
                typer.echo(f"{name}: OK  provider={getattr(resp, 'provider', '?')}  {content}")
            except ValidationError as e:
                typer.echo(f"{name}: INVALID  {e.errors()[0]['msg']}  {content}")
            except Exception as e:
                typer.echo(f"{name}: ERROR  {type(e).__name__}: {str(e)[:200]}")

    typer.echo(f"model={model()}")
    asyncio.run(run())
    typer.echo(json.dumps({"hint": "set LLM_JSON_SCHEMA=true in .env if json_schema is OK"}))


from preflight.eval.cli import register  # noqa: E402  (B's fetch / inject / bench commands)

register(app)

if __name__ == "__main__":
    app()
