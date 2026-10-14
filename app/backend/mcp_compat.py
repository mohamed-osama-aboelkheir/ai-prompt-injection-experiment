"""
Tiny adapter so the MCP servers keep their plain `list_tools()` / `call_tool(name, args)`
functions while running on the mcp 2.x low-level Server, which takes handlers as
constructor callbacks instead of the 1.x `@server.list_tools()` decorators.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from mcp.server import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


def build_server(
    name: str,
    list_tools: Callable[[], Awaitable[list[Tool]]],
    call_tool: Callable[[str, dict], Awaitable[list[TextContent]]],
) -> Server:
    async def _on_list_tools(ctx, params) -> ListToolsResult:
        return ListToolsResult(tools=await list_tools())

    async def _on_call_tool(ctx, params) -> CallToolResult:
        return CallToolResult(content=await call_tool(params.name, params.arguments or {}))

    return Server(name, on_list_tools=_on_list_tools, on_call_tool=_on_call_tool)
