import asyncio
from jsonschema import ValidationError, validate
from harness.tools.base import Tool, ToolResult

async def dispatch(tool:Tool, args: dict, Timeout: float = 10.0)->ToolResult:
    try:
        validate(instance = args, schema = tool.parameter)
    except ValidationError as e:
        return ToolResult(ok = False, content = f"Invalid arguments for {tool.name} : {e.message}")
    
    try:
        result = await asyncio.wait_for(tool.handler(**args), timeout = Timeout)
        return ToolResult(ok = True, content = str(result))
    except asyncio.TimeoutError:
        return ToolResult(ok = False, content = f"Tool {tool.name} timeouts after {timeout}s")
    
    except Exception as e:
        return ToolResult(ok = False, content = f"Tool {tool.name} failed {e}")

