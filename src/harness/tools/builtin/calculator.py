import ast
import operator
from harness.tools.base import Tool

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.Mod: operator.mod,
}

def _eval(node: ast.AST)->float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expresion")

async def calculate(expression:str)->str:
    tree = ast.parse(expression, mode="eval")
    return str(_eval(tree.body))

CALCULATOR_TOOL = Tool(
    name = "calculator",
    description = "Evaluate a basic arithmetic expression like '2 + 2 * 3'.",
    parameter = {
        "type": "object",
        "properties": {"expression":{"type": "string"}},
        "required": ["expression"],
    },
    handler = calculate
)