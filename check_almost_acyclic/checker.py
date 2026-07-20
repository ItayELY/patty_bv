"""Check whether a PDDL domain is "almost acyclic with integer self-loops":

1. The dependency variable-dependency graph G, restricted to edges between
   *distinct* variables (self-loops excluded), is acyclic.
2. For every numeric effect on a variable y, the coefficient z of y in its
   own right-hand side (y := z*y + sum c_v*v) is an integer.

Condition 1 reuses causal_cycles' influence graph builder (the graph it
already computes for cycle-detection is exactly G, self-loops included).
Condition 2 is checked per numeric effect via linear_form.self_coefficient.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from causal_cycles.graph import DiGraph
from causal_cycles.influence_graph import build_influence_graph

from check_almost_acyclic.linear_form import NumericEffect, iter_numeric_effects, self_coefficient


@dataclass
class SelfLoopViolation:
    effect: NumericEffect
    coefficient: Optional[object]  # sympy Rational, or None if non-linear
    witness: object  # sympy Expr: the coefficient itself, or the non-constant expression found instead

    @property
    def reason(self) -> str:
        if self.coefficient is None:
            return (f"self-coefficient of '{self.effect.target}' is not a constant "
                    f"(depends on other variable(s)): z = {self.witness}")
        return f"self-coefficient of '{self.effect.target}' is z = {self.coefficient}, not an integer"

    def __str__(self) -> str:
        return (f"action '{self.effect.action_name}', effect {self.effect}: {self.reason}")


@dataclass
class AlmostAcyclicResult:
    graph: DiGraph
    cycles: List[List[str]] = field(default_factory=list)
    self_loop_violations: List[SelfLoopViolation] = field(default_factory=list)

    @property
    def condition1_ok(self) -> bool:
        return not self.cycles

    @property
    def condition2_ok(self) -> bool:
        return not self.self_loop_violations

    @property
    def is_almost_acyclic(self) -> bool:
        return self.condition1_ok and self.condition2_ok


def _non_trivial_cycles(graph: DiGraph) -> List[List[str]]:
    """Cycles among >=2 distinct variables - self-loops don't count, they're
    exactly what condition 2 permits (provided their coefficient is integer)."""
    return [c for c in graph.strongly_connected_components() if len(c) > 1]


def check_domain_text(domain_text: str) -> AlmostAcyclicResult:
    graph = build_influence_graph(domain_text)
    cycles = sorted(_non_trivial_cycles(graph), key=lambda c: (-len(c), c))

    violations: List[SelfLoopViolation] = []
    for effect in iter_numeric_effects(domain_text):
        result = self_coefficient(effect)
        if not result.is_integer:
            violations.append(SelfLoopViolation(effect=effect, coefficient=result.value, witness=result.expr))

    return AlmostAcyclicResult(graph=graph, cycles=cycles, self_loop_violations=violations)


def check_domain_file(path: str) -> AlmostAcyclicResult:
    text = Path(path).read_text()
    return check_domain_text(text)
