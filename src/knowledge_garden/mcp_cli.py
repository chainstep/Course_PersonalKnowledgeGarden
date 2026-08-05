from __future__ import annotations

import asyncio
import json

import typer

from .config import Settings
from .mcp.client import MCPClient

app = typer.Typer(no_args_is_help=True)


def call(tool: str, arguments: dict) -> object:
    return asyncio.run(MCPClient(Settings.from_env()).call(tool, arguments))


def output(value: object, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(value, default=str, ensure_ascii=False))
    elif isinstance(value, str):
        typer.echo(value, nl=False)
    else:
        typer.echo(json.dumps(value, default=str, ensure_ascii=False, indent=2))


@app.command()
def add(
    file: str,
    tag: list[str] = typer.Option([], "--tag"),
    type: str | None = typer.Option(None, "--type"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    output(call("add", {"file": file, "tags": tag, "type": type}), json_output)


@app.command()
def search(query: str, limit: int = 20, json_output: bool = typer.Option(False, "--json")) -> None:
    output(call("search", {"query": query, "limit": limit}), json_output)


@app.command()
def recent(
    hours: int = 24, limit: int = 20, json_output: bool = typer.Option(False, "--json")
) -> None:
    output(call("recent", {"hours": hours, "limit": limit}), json_output)


@app.command()
def fetch(item_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    output(call("fetch", {"item_id": item_id}), json_output)


@app.command()
def digest(hours: int = 24, output_path: str | None = typer.Option(None, "--output")) -> None:
    output(call("digest", {"hours": hours, "output": output_path}), False)


@app.command()
def reindex(force: bool = False, json_output: bool = typer.Option(False, "--json")) -> None:
    output(call("reindex", {"force": force}), json_output)


@app.command()
def curate(request: str) -> None:
    output(call("curate", {"request": request}), False)


@app.command()
def quiz(topic: str) -> None:
    output(call("quiz", {"topic": topic}), False)


@app.command()
def version() -> None:
    output(call("version", {}), False)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
