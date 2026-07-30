import asyncio
from harness.tools.registry import ToolRegistry
from harness.tools.dispatch import dispatch
from harness.tools.builtin.calculator import CALCULATOR_TOOL

reg = ToolRegistry()
reg.registry(CALCULATOR_TOOL)

async def main():
    tool = reg.get("calculator")
    print(await dispatch(tool, {"expression": "2 + 2 * 3"}))   # ok=True content='8'
    print(await dispatch(tool, {"wrong": "2+2"}))              # ok=False invalid args
    print(await dispatch(tool, {"expression": "import os"}))   # ok=False failed, no crash

asyncio.run(main())