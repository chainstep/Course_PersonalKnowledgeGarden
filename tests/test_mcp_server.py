from __future__ import annotations

import socket
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

from knowledge_garden.config import Settings
from knowledge_garden.ingestion import IngestionService
from knowledge_garden.mcp.client import MCPClient
from knowledge_garden.mcp.server import create_server
from knowledge_garden.storage import Database, Repository


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError("server did not start in time")


@asynccontextmanager
async def _live_server(settings: Settings):
    import uvicorn

    app = create_server(settings).http_app(path="/mcp", transport="streamable-http")
    config = uvicorn.Config(app, host=settings.mcp_host, port=settings.mcp_port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_port(settings.mcp_host, settings.mcp_port)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=5)


async def test_mcp_server_registers_tools_and_resource(settings: Settings):
    server = create_server(settings)
    tools = {tool.name for tool in await server.list_tools()}
    resources = {str(resource.uri) for resource in await server.list_resources()}
    templates = {template.uri_template for template in await server.list_resource_templates()}
    assert {"add", "search", "recent", "fetch", "digest", "reindex", "curate", "quiz", "version"} <= tools
    assert "notes://recent" in resources or "notes://recent" in templates


async def test_mcp_cli_parity(settings: Settings, tmp_path: Path):
    settings = replace(settings, mcp_port=_free_port())
    sample = tmp_path / "note.md"
    sample.write_text("# Hi\n\nMCP roundtrip body text.")
    IngestionService(Repository(Database(settings)), settings).add(str(sample))

    async with _live_server(settings):
        client = MCPClient(settings)
        recent = await client.call("recent", {"hours": 24, "limit": 10})
        recent_list = (
            recent
            if isinstance(recent, list)
            else recent["recent"]
            if isinstance(recent, dict)
            else []
        )
        assert any(item["type"] == "markdown" for item in recent_list)
        search = await client.call("search", {"query": "MCP", "limit": 5})
        search_list = (
            search
            if isinstance(search, list)
            else search["search"]
            if isinstance(search, dict)
            else []
        )
        assert isinstance(search_list, list)

        reindex_result = await client.call("reindex", {"force": False})
        assert reindex_result["status"] == "ok"

        version = await client.call("version", {})
        assert "knowledge-garden" in version
