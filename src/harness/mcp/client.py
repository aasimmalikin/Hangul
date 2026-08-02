"""Wraps one MCP server connection over stdio, keeping the session open so tools
can be called repeatedly."""

from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    def __init__(self, command: str, args: list[str])-> None:
        self._params = StdioServerParameters(command = command, args = args)
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
    
    async def connect(self)->None:
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
    
    async def list_tools(self)-> list[str]:
        assert self._session is not None
        return (await self._session.list_tools()).tools
    
    async def call_tool(self, name:str, arguments: str)-> str:
        assert self._session is not None
        result = await self._session.call_tool(name, arguments)
        return "".join(b.text for b in result.content if hasattr(b, "text"))
    
    async def close(self)->None:
        await self._stack.aclose()