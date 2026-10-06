"""Does a function introduce a fitted parameter? Answered from CODE, never from prose.

B17/B18 were selected after reading hold-out results, and what keeps that defensible is that they
fit nothing. The first guard for that scanned source text for "threshold" and matched the
docstring sentence saying B17 is NOT a threshold -- prose about the absence of a parameter is not
a parameter. The check lives here, as a function, so that the docstring failure can itself be
reintroduced by mutation and shown to be caught (`error_registry.py`, `ast_guard_docstring`).
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Callable, Set

BANNED = {"thr", "threshold", "thresholds", "weight", "weights", "coef", "coefs", "fit",
          "model", "scores", "score"}


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]


def fitted_parameter_references(func: Callable) -> Set[str]:
    """Banned identifiers or string constants used in the function's CODE (docstrings excluded)."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    _strip_docstrings(tree)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    strings = {n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return (names | strings) & BANNED
