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

# Refusing eval() blocks code execution, but plain arithmetic can still hang the
# process: "9**9**9" asks Python to build a ~370-million-digit integer, which
# pins CPU and memory long enough to be a denial of service. We never need an
# exponent that large for a real question, so we cap it and reject the rest. The
# exponent is checked before the power is computed, so the huge number is never
# built in the first place.
MAX_EXPONENT = 1000


def _eval(node):
    # bool is a subclass of int, so guard against it to keep "True" out of maths.
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ValueError(f"exponent too large (max {MAX_EXPONENT})")
        return _OPS[type(node.op)](left, right)
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
