"""Adapt MCP tools into the harness Tool shape."""

from harness.mcp.client import MCPClient
from harness.tools.base import Tool


def adapt_mcp_tool(client: MCPClient, mcp_tools: list) -> list[Tool]:
    tools: list[Tool] = []
    for mt in mcp_tools:
        schema = mt.inputSchema or {}
        required = schema.get("required", [])

        def make_handler(tool_name: str, required_fields: list):
            async def handler(**kwargs) -> str:
                # If the model omitted a required 'path', default it to "." (the
                # filesystem server's root). Prevents the empty-args retry loop.
                if "path" in required_fields and not kwargs.get("path"):
                    kwargs["path"] = "."
                return await client.call_tool(tool_name, kwargs)
            return handler

        tools.append(Tool(
            name=mt.name,
            description=mt.description or "",
            parameter=schema,
            handler=make_handler(mt.name, required),
        ))
    return tools
