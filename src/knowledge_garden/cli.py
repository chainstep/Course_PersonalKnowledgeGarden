from __future__ import annotations

import json

import typer

from .config import Settings
from .digest import write_digest
from .ingestion import IngestionService
from .reindex import reindex
from .search import SearchService
from .storage import Database, Repository

app = typer.Typer(no_args_is_help=True)


def services():
    settings = Settings.from_env()
    repository = Repository(Database(settings))
    return settings, repository


def emit(value, as_json: bool = False) -> None:
    if as_json:
        typer.echo(
            json.dumps(
                value,
                default=lambda item: item.isoformat() if hasattr(item, "isoformat") else str(item),
                ensure_ascii=False,
            )
        )
    else:
        if isinstance(value, str):
            typer.echo(value, nl=False)
        else:
            typer.echo(value)


@app.command()
def add(
    file: str,
    tag: list[str] = typer.Option([], "--tag"),
    type: str | None = typer.Option(None, "--type"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    settings, repository = services()
    result = IngestionService(repository, settings).add(file, tag, type)
    payload = result.model_dump(mode="json")
    if json_output:
        emit(payload, True)
    else:
        typer.echo(
            f"{result.item.id} chunks={result.chunk_count} neutralized_spans={result.neutralized_spans}"
        )


@app.command()
def search(query: str, limit: int = 20, json_output: bool = typer.Option(False, "--json")) -> None:
    settings, repository = services()
    safe_query = " ".join(f'"{part.replace(chr(34), "")}"' for part in query.split())
    hits = SearchService(repository, settings).search(safe_query, limit)
    emit([hit.model_dump(mode="json") for hit in hits], json_output)


@app.command()
def recent(
    hours: int = 24, limit: int = 20, json_output: bool = typer.Option(False, "--json")
) -> None:
    _, repository = services()
    items = repository.recent(hours, limit)
    emit([item.model_dump(mode="json") for item in items], json_output)


@app.command()
def fetch(item_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    _, repository = services()
    value = repository.fetch(item_id)
    if value is None:
        raise typer.BadParameter("item not found")
    item, chunks = value
    emit(
        {
            "item": item.model_dump(mode="json"),
            "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
        },
        json_output,
    )


@app.command()
def digest(hours: int = 24, output: str | None = None) -> None:
    _, repository = services()
    emit(write_digest(repository.recent(hours, 1000), hours, output))


@app.command()
def reindex_command(
    force: bool = typer.Option(False, "--force", help="Allow embedding model changes."),
    json_output: bool = typer.Option(False, "--json"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress output (for cron/CI)."),
) -> None:
    settings = Settings.from_env()
    count = reindex(settings, force)
    if not quiet:
        emit({"vectors": count, "status": "ok"} if json_output else f"reindexed {count} vectors")


app.command("reindex")(reindex_command)


@app.command()
def serve(port: int | None = None) -> None:
    from .mcp.server import run_server

    settings = Settings.from_env()
    run_server(settings, port or settings.mcp_port)


@app.command()
def curate(request: str) -> None:
    from .agents.runner import run_curator

    emit(run_curator(request))


@app.command()
def quiz(topic: str) -> None:
    from .agents.runner import run_quiz

    emit(run_quiz(topic))


@app.command()
def version() -> None:
    typer.echo("knowledge-garden 0.1.0")


def main() -> None:
    """Console entry point: map typed domain errors to exit code 3."""
    from .models import DomainError

    try:
        app()
    except DomainError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
