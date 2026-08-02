import asyncio

from jsonschema import ValidationError, validate

from harness.tools.base import Tool, ToolResult


async def dispatch(tool: Tool, args: dict, timeout: float = 10.0) -> ToolResult:
    try:
        validate(instance=args, schema=tool.parameter)
    except ValidationError as e:
        # A helpful, self-correcting error: tell the model exactly what's missing
        # and how to fix it, so it retries with valid args instead of looping.
        required = tool.parameter.get("required", []) if isinstance(tool.parameter, dict) else []
        hint = ""
        if "path" in required:
            hint = " For filesystem tools, use path '.' for the docs folder itself, or a bare filename like 'report.txt'."
        return ToolResult(
            ok=False,
            content=f"Invalid arguments for {tool.name}: {e.message}. Required fields: {required}.{hint}",
        )

    try:
        result = await asyncio.wait_for(tool.handler(**args), timeout=timeout)
        return ToolResult(ok=True, content=str(result))
    except asyncio.TimeoutError:
        return ToolResult(ok=False, content=f"Tool {tool.name} timed out after {timeout}s")
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, content=f"Tool {tool.name} failed: {e}")
