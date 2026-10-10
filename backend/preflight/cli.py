import typer
import uvicorn

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    uvicorn.run("preflight.api.main:app", host=host, port=port, reload=reload)


@app.command()
def check(path: str):
    typer.echo(f"check not implemented yet: {path}")


if __name__ == "__main__":
    app()
