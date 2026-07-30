from harness.tools.base import Tool

def to_openai_tool(tool: Tool)->dict:
    """Render a Tool as an OpenAI tool spec — the same JSON Schema, wrapped."""
    return{
        "type":"function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameter": tool.parameter,
        },
    }