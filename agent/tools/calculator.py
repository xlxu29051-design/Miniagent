"""Safe arithmetic calculator: evaluates expressions via AST (no eval)."""
from __future__ import annotations

import ast
import math
import operator
from typing import Any

from .base import ToolError, ToolRegistry

_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "log": math.log,
          "sin": math.sin, "cos": math.cos, "tan": math.tan, "pi": math.pi, "e": math.e}


def _eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ToolError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _FUNCS and not callable(_FUNCS[node.id]):
        return _FUNCS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _FUNCS.get(node.func.id)
        if fn is None or not callable(fn):
            raise ToolError(f"unsupported function: {node.func.id}")
        return fn(*[_eval(a) for a in node.args])
    raise ToolError("unsupported expression")


def calculate(expression: str) -> Any:
    if not isinstance(expression, str) or not expression.strip():
        raise ToolError("expression must be a non-empty string")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"could not parse expression: {exc}") from exc
    return {"expression": expression, "result": _eval(tree)}


def register(registry: ToolRegistry) -> None:
    from .base import Tool
    registry.register(Tool(
        name="calculator",
        description="Evaluate an arithmetic expression. Supports + - * / // % ** parentheses "
        "and functions like sqrt, abs, round, log, sin.",
        parameters={"type": "object",
                    "properties": {"expression": {"type": "string",
                        "description": "e.g. '(2 + 3) * 4' or 'sqrt(144)'."}},
                    "required": ["expression"]},
        func=calculate))