"""Build a directed "influence graph" between PDDL numeric variables.

A node is a fluent/function symbol (e.g. ``x`` in ``(x ?obj)``) - all
instantiations of that function share one node, since we work at the
schema (lifted) level rather than on a grounded problem.

An edge ``y -> x`` means some action/process/event effect assigns (via
``assign``/``increase``/``decrease``/``scale-up``/``scale-down``) a new
value to ``x`` using an expression that reads ``y``. ``x := 2 * x`` yields
a self-loop ``x -> x``; ``x := y + 1`` yields ``y -> x``.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

from causal_cycles.graph import DiGraph
from causal_cycles.sexpr import SExpr, head, parse_all

_NUMERIC_EFFECT_OPS = {"assign", "increase", "decrease", "scale-up", "scale-down"}
_ARITHMETIC_OPS = {"+", "-", "*", "/"}
_OP_SECTION_KEYWORDS = {":action", ":process", ":event", ":durative-action"}


def _function_symbol(expr: SExpr) -> Optional[str]:
    """The fluent name of a function-application term, e.g. (x ?a) -> 'x'."""
    if isinstance(expr, list) and expr and isinstance(expr[0], str):
        return expr[0]
    return None


def _collect_function_refs(expr: SExpr, refs: Set[str]) -> None:
    if not isinstance(expr, list) or not expr:
        return
    h = head(expr)
    if h in _ARITHMETIC_OPS:
        for sub in expr[1:]:
            _collect_function_refs(sub, refs)
    else:
        sym = _function_symbol(expr)
        if sym is not None:
            refs.add(sym)


def _walk_effect(expr: SExpr, action_name: str, graph: DiGraph) -> None:
    if not isinstance(expr, list) or not expr:
        return
    h = head(expr)

    if h == "and":
        for sub in expr[1:]:
            _walk_effect(sub, action_name, graph)
    elif h == "forall" and len(expr) >= 3:
        _walk_effect(expr[2], action_name, graph)
    elif h == "when" and len(expr) >= 3:
        _walk_effect(expr[2], action_name, graph)
    elif h == "at" and len(expr) == 3 and str(expr[1]).lower() in ("start", "end"):
        _walk_effect(expr[2], action_name, graph)
    elif h in _NUMERIC_EFFECT_OPS and len(expr) >= 3:
        target = _function_symbol(expr[1])
        if target is None:
            return
        graph.add_node(target)
        refs: Set[str] = set()
        _collect_function_refs(expr[2], refs)
        for src in refs:
            graph.add_edge(src, target, label=action_name)
    # boolean add/delete effects (bare literal, or ("not" literal)) carry no
    # numeric influence and are intentionally ignored.


def _iter_function_declarations(functions_section: SExpr) -> List[str]:
    """Names declared in a (:functions (x ?a - t) (y) - number ...) block."""
    names: List[str] = []
    if not isinstance(functions_section, list):
        return names
    for item in functions_section[1:]:
        if isinstance(item, list) and item and isinstance(item[0], str):
            names.append(item[0])
    return names


def _op_name(section: SExpr) -> str:
    # (:action NAME :parameters (...) ...) -> NAME is section[1]
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


def build_influence_graph(domain_text: str) -> DiGraph:
    graph = DiGraph()

    forms = parse_all(domain_text)
    define_form = next((f for f in forms if head(f) == "define"), None)
    if define_form is None:
        return graph

    for section in define_form:
        if not isinstance(section, list) or not section or not isinstance(section[0], str):
            continue
        keyword = section[0].lower()

        if keyword == ":functions":
            for name in _iter_function_declarations(section):
                graph.add_node(name)
        elif keyword in _OP_SECTION_KEYWORDS:
            effect_expr = _op_effect_expr(section)
            if effect_expr is not None:
                _walk_effect(effect_expr, _op_name(section), graph)

    return graph


def build_influence_graph_from_file(path: str) -> DiGraph:
    text = Path(path).read_text()
    return build_influence_graph(text)
