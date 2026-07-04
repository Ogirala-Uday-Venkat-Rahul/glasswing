"""A safe arithmetic evaluator.

The point of this tool in the demo: the agent delegates arithmetic instead of
guessing it. So it has to actually be correct, and it has to be safe. We do NOT
use eval(), because eval() on model-supplied text is remote code execution. We
parse the expression to an AST and walk only the numeric-operator nodes, so
anything that is not plain arithmetic is rejected.
"""

import ast
import operator

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    # Names, function calls, attribute access, strings: all refused here.
    raise ValueError("only plain arithmetic is allowed")


def calculator(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    return str(_eval(tree.body))


SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": (
            "Evaluate a basic arithmetic expression using + - * / ** and %. "
            "Always use this for calculations instead of computing them yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The expression to evaluate, e.g. '37 * (12 + 5)'",
                }
            },
            "required": ["expression"],
        },
    },
}
