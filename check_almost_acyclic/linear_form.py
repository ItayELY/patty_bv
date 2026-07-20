"""Extract numeric effects from a PDDL domain and, for each one, the
coefficient of the *target* variable in its own right-hand side.

Given a numeric effect on variable ``y`` (schema/lifted level, so ``(fuel
?t)`` and ``(fuel ?other)`` are both just the variable ``fuel``), we rewrite
it into the form::

    y := z*y + c_1*v_1 + ... + c_n*v_n

and return ``z``, the *self coefficient*. This is exactly the ``z`` from the
"almost acyclic with integer self-loops" definition: condition 2 requires
``z`` to be an integer for every numeric effect.

Effects recognized: ``assign``, ``increase``, ``decrease``, ``scale-up``,
``scale-down``, including ones nested in ``and``, ``forall``, ``when``, and
durative-action ``(at start ...)``/``(at end ...)`` wrappers - mirrors the
traversal in ``causal_cycles.influence_graph``.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator, Optional

import sympy as sp

from causal_cycles.sexpr import SExpr, head, parse_all

_NUMERIC_EFFECT_OPS = {"assign", "increase", "decrease", "scale-up", "scale-down"}
_ARITHMETIC_OPS = {"+", "-", "*", "/"}
_OP_SECTION_KEYWORDS = {":action", ":process", ":event", ":durative-action"}


@dataclass
class NumericEffect:
    action_name: str
    operator: str
    target: str
    rhs: SExpr
    raw: SExpr

    def __str__(self) -> str:
        return _to_text(self.raw)


@dataclass
class CoefficientResult:
    """Result of computing the self-coefficient ``z`` of a numeric effect.

    ``value`` is the coefficient as a sympy Rational when the effect is
    linear in its target variable; ``None`` when the "coefficient" actually
    depends on some other variable (the effect is not of the required
    ``y := z*y + sum c_v*v`` linear form at all), in which case ``expr``
    holds the offending (non-constant) expression as a witness.
    """
    value: Optional[sp.Rational]
    expr: sp.Expr

    @property
    def is_integer(self) -> bool:
        return self.value is not None and self.value.is_Integer


def _to_text(expr: SExpr) -> str:
    if isinstance(expr, list):
        return "(" + " ".join(_to_text(e) for e in expr) + ")"
    return str(expr)


def _function_symbol(expr: SExpr) -> Optional[str]:
    """The fluent name of a function-application term, e.g. (x ?a) -> 'x'."""
    if isinstance(expr, list) and expr and isinstance(expr[0], str):
        return expr[0]
    return None


def _is_number(tok: str) -> bool:
    try:
        Fraction(tok)
        return True
    except (ValueError, ZeroDivisionError):
        return False


def to_sympy(expr: SExpr) -> sp.Expr:
    """Convert a numeric S-expression into a sympy expression.

    Function applications become sympy Symbols keyed by function *name*
    only (schema level - all instantiations of a function share one
    symbol), numeric tokens become exact sympy Rationals (never floats, so
    integrality checks on the resulting coefficients are exact).
    """
    if isinstance(expr, str):
        if _is_number(expr):
            f = Fraction(expr)
            return sp.Rational(f.numerator, f.denominator)
        return sp.Symbol(expr)

    if not isinstance(expr, list) or not expr:
        raise ValueError(f"cannot convert expression: {expr!r}")

    h = head(expr)
    if h in _ARITHMETIC_OPS:
        args = [to_sympy(a) for a in expr[1:]]
        if not args:
            raise ValueError(f"arithmetic operator with no operands: {expr!r}")
        if h == "+":
            return sp.Add(*args)
        if h == "-":
            if len(args) == 1:
                return -args[0]
            result = args[0]
            for a in args[1:]:
                result -= a
            return result
        if h == "*":
            return sp.Mul(*args)
        if h == "/":
            result = args[0]
            for a in args[1:]:
                result /= a
            return result

    sym_name = _function_symbol(expr)
    if sym_name is None:
        raise ValueError(f"cannot convert expression: {expr!r}")
    return sp.Symbol(sym_name)


def self_coefficient(effect: NumericEffect) -> CoefficientResult:
    """Compute z where effect rewrites as target := z*target + (rest)."""
    target_sym = sp.Symbol(effect.target)
    rhs_expr = to_sympy(effect.rhs)

    if effect.operator == "assign":
        full = rhs_expr
    elif effect.operator == "increase":
        full = target_sym + rhs_expr
    elif effect.operator == "decrease":
        full = target_sym - rhs_expr
    elif effect.operator == "scale-up":
        full = target_sym * rhs_expr
    elif effect.operator == "scale-down":
        full = target_sym / rhs_expr
    else:
        raise ValueError(f"unknown numeric effect operator: {effect.operator}")

    z = sp.simplify(sp.diff(sp.expand(full), target_sym))

    if z.free_symbols:
        return CoefficientResult(value=None, expr=z)
    return CoefficientResult(value=sp.nsimplify(z), expr=z)


def _iter_effect_forms(expr: SExpr, action_name: str) -> Iterator[NumericEffect]:
    if not isinstance(expr, list) or not expr:
        return
    h = head(expr)

    if h == "and":
        for sub in expr[1:]:
            yield from _iter_effect_forms(sub, action_name)
    elif h == "forall" and len(expr) >= 3:
        yield from _iter_effect_forms(expr[2], action_name)
    elif h == "when" and len(expr) >= 3:
        yield from _iter_effect_forms(expr[2], action_name)
    elif h == "at" and len(expr) == 3 and str(expr[1]).lower() in ("start", "end"):
        yield from _iter_effect_forms(expr[2], action_name)
    elif h in _NUMERIC_EFFECT_OPS and len(expr) >= 3:
        target = _function_symbol(expr[1])
        if target is not None:
            yield NumericEffect(action_name=action_name, operator=h, target=target, rhs=expr[2], raw=expr)


def _op_name(section: SExpr) -> str:
    if isinstance(section, list) and len(section) >= 2 and isinstance(section[1], str):
        return section[1]
    return head(section)


def _op_effect_expr(section: SExpr) -> Optional[SExpr]:
    if not isinstance(section, list):
        return None
    for i, item in enumerate(section):
        if isinstance(item, str) and item.lower() in (":effect", ":effects"):
            if i + 1 < len(section):
                return section[i + 1]
    return None


def iter_numeric_effects(domain_text: str) -> Iterator[NumericEffect]:
    """Every numeric (assign/increase/decrease/scale-up/scale-down) effect
    in a PDDL domain's actions/events/processes."""
    forms = parse_all(domain_text)
    define_form = next((f for f in forms if head(f) == "define"), None)
    if define_form is None:
        return

    for section in define_form:
        if not isinstance(section, list) or not section or not isinstance(section[0], str):
            continue
        keyword = section[0].lower()
        if keyword not in _OP_SECTION_KEYWORDS:
            continue
        effect_expr = _op_effect_expr(section)
        if effect_expr is not None:
            yield from _iter_effect_forms(effect_expr, _op_name(section))
