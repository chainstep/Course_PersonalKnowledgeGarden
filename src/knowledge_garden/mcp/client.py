from __future__ import annotations

import json
from typing import Any

from ..config import Settings


class MCPClient:
    def __init__(self, settings: Settings) -> None:
        self.url = f"http://{settings.mcp_host}:{settings.mcp_port}/mcp"

    async def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async with (
            streamable_http_client(self.url) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            payload = _extract_payload(result)
            if (
                isinstance(payload, dict)
                and "result" in payload
                and isinstance(payload["result"], (list, str))
            ):
                return payload["result"]
            return payload


def _extract_payload(result: object) -> object:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", [])
    if content and hasattr(content[0], "text"):
        try:
            return json.loads(content[0].text)
        except json.JSONDecodeError:
            return content[0].text
    return result
