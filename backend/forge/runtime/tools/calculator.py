"""Safe arithmetic via an AST whitelist (never eval)."""

from __future__ import annotations

import ast
import math
import operator
import re

from pydantic import BaseModel, Field

from forge.runtime.tools.base import Tool

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"round": round, "min": min, "max": max, "abs": abs, "sqrt": math.sqrt}


class CalcArgs(BaseModel):
    expression: str = Field(description="Arithmetic expression, e.g. '12 * 345.5 * 1.18'", max_length=200)


def safe_eval(expr: str) -> float:
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", expr).replace("^", "**")  # 1,200 -> 1200, keeps min(1, 2)
    tree = ast.parse(cleaned, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1e6):
                raise ValueError("exponent too large")
            return _BIN[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS \
                and not node.keywords:
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"unsupported expression element: {ast.dump(node)[:60]}")

    return ev(tree)


class CalculatorTool(Tool):
    name = "calculator"
    description = ("Evaluate an arithmetic expression exactly. Use it for every total, sum, difference, "
                   "percentage, conversion or quantity x price instead of doing maths yourself.")
    Args = CalcArgs

    def _run(self, args: CalcArgs):
        value = safe_eval(args.expression)
        if isinstance(value, float):
            value = round(value, 6)
        return {"expression": args.expression, "result": value}
