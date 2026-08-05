from __future__ import annotations

import json
from typing import Any

from ..config import Settings
from ..digest import render_digest
from ..ingestion import IngestionService
from ..reindex import reindex
from ..search import SearchService
from ..storage import Database, Repository


def create_server(settings: Settings):
    from fastmcp import FastMCP

    server = FastMCP("knowledge-garden")
    repository = Repository(Database(settings))

    @server.tool()
    def add(file: str, tags: list[str] | None = None, type: str | None = None) -> dict[str, Any]:
        return (
            IngestionService(repository, settings)
            .add(file, tags or [], type)
            .model_dump(mode="json")
        )

    @server.tool()
    def search(query: str, limit: int = 20) -> list[dict[str, Any]]:
        return [
            hit.model_dump(mode="json")
            for hit in SearchService(repository, settings).search(query, limit)
        ]

    @server.tool()
    def recent(hours: int = 24, limit: int = 20) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in repository.recent(hours, limit)]

    @server.tool()
    def fetch(item_id: str) -> dict[str, Any]:
        result = repository.fetch(item_id)
        if result is None:
            return {"error": "item not found"}
        item, chunks = result
        return {
            "item": item.model_dump(mode="json"),
            "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
        }

    @server.tool()
    def digest(hours: int = 24, output: str | None = None) -> str:
        text = render_digest(repository.recent(hours, 1000), hours)
        if output:
            from pathlib import Path

            Path(output).expanduser().write_text(text, encoding="utf-8")
        return text

    @server.tool(name="reindex")
    def reindex_tool(force: bool = False) -> dict[str, Any]:
        return {"vectors": reindex(settings, force), "status": "ok"}

    @server.tool(name="curate")
    def curate_tool(request: str) -> str:
        from ..agents.runner import run_curator

        return run_curator(request)

    @server.tool(name="quiz")
    def quiz_tool(topic: str) -> str:
        from ..agents.runner import run_quiz

        return run_quiz(topic)

    @server.tool(name="version")
    def version_tool() -> str:
        return "knowledge-garden 0.1.0"

    @server.resource("notes://recent")
    def recent_resource() -> str:
        return json.dumps(recent(), ensure_ascii=False)

    return server


def run_server(settings: Settings, port: int) -> None:
    settings = Settings(
        settings.data_dir,
        settings.db_path,
        settings.mcp_host,
        port,
        settings.embed_backend,
        settings.embedding_model,
        settings.embedding_dim,
        settings.sanitizer_version,
    )
    create_server(settings).run(transport="streamable-http", host=settings.mcp_host, port=port)
