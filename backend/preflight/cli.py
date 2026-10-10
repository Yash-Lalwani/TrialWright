import typer
import uvicorn

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    uvicorn.run("preflight.api.main:app", host=host, port=port, reload=reload)


@app.command()
def check(path: str):
    typer.echo(f"check not implemented yet: {path}")


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


if __name__ == "__main__":
    app()
