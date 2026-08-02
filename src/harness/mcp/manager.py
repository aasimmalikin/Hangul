"""Connect to multiple MCP servers, adapt all their tools into one registry, with
namespacing (every tool prefixed by its server) and shadowing detection (flag a
tool that collides with one another server already owns)."""

from harness.mcp.adapter import adapt_mcp_tool
from harness.mcp.client import MCPClient
from harness.tools.base import Tool
from harness.tools.registry import ToolRegistry

class MCPManager:
    def __init__(self)->None:
        self._clients: list[MCPClient] = []
        self._owner: dict[str, str] = {}
        self._alerts: list[str] = []
    
    async def add_server(self, name:str, command:str, args: list[str], registry: ToolRegistry)->None:
        client = MCPClient(command, args)
        await client.connect()
        self._clients.append(client)
        
        for tool in adapt_mcp_tool(client, await client.list_tools()):
            namespaced = f"{name}__{tool.name}"
            if namespaced in self._owner:
                self._alerts.append(f"Shadowing server {name} tool {tool.name} collides with {self._owner[namespaced]}")
                continue
            self._owner[namespaced] = None
            registry.registry(Tool(
                name = namespaced,
                description = f"[{name}] {tool.description}",
                parameter = tool.parameter,
                handler = tool.handler,
            ))
    
    async def close(self)->None:
        for client in self._clients:
            await client.close()

            