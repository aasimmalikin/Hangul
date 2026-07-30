from harness.tools.base import Tool

class ToolRegistry():
    def __init__(self)->None:
        self._tools: dict[str, Tool] = {}
    
    def registry(self, tool:Tool)->None:
        self._tools[tool.name] = tool
    
    def get(self, name: str)->Tool:
        if name not in self._tools:
            raise KeyError(f"Unkown tool {name}")
        return self._tools[name]
    
    def list(self)->list[Tool]:
        return list(self._tools.values())