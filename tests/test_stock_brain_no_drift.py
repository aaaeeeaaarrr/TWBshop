"""Cross-lane DRIFT GUARD (integrator-owned).

`gm_bot/stock.py` (GM lane, owner-test-gated) and `stock/order_brain.py` (the stock-lane port) are
DUPLICATES until the integrator cutover removes the GM copy. Neither lane can see the other, so a
pre-cutover edit to either could silently drift. This asserts their LOGIC stays identical (docstrings
ignored) — a drift turns the suite red instead of going unnoticed. Skips automatically once one copy
is removed (i.e. the cutover happened), so it never blocks the cutover itself.
"""
import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GM_COPY = os.path.join(ROOT, "gm_bot", "stock.py")
STOCK_COPY = os.path.join(ROOT, "stock", "order_brain.py")


def _logic(path):
    """AST of the module with every docstring stripped — compares logic, ignores prose."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(getattr(node.body[0], "value", None), ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
    return ast.dump(tree)


@pytest.mark.skipif(not (os.path.exists(GM_COPY) and os.path.exists(STOCK_COPY)),
                    reason="one copy removed — integrator cutover done, drift guard no longer needed")
def test_order_brain_copies_have_not_drifted():
    assert _logic(GM_COPY) == _logic(STOCK_COPY), (
        "gm_bot/stock.py and stock/order_brain.py have DRIFTED apart. They must stay logic-identical "
        "until the GM↔stock cutover removes the GM copy — sync them, or do the cutover.")
