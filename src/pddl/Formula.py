from __future__ import annotations

import copy

from itertools import chain
from typing import Dict, List, Set, Tuple

from src.pddl.Atom import Atom
from src.pddl.BinaryPredicate import BinaryPredicate
from src.pddl.Literal import Literal
from src.pddl.Predicate import Predicate
from src.pddl.Utilities import Utilities
from src.pddl.grammar.pddlParser import pddlParser as p


def _isObjectVar(operationSideNode) -> str | None:
    """Return the variable name if the node is a bare object variable (?x), else None."""
    if operationSideNode is None or operationSideNode.getChildCount() == 0:
        return None
    child = operationSideNode.getChild(0)
    if not isinstance(child, p.PositiveLiteralContext):
        return None
    # A bare ?x is parsed as PositiveLiteralContext with one LiftedAtomParameterContext child
    if child.getChildCount() == 1 and isinstance(child.getChild(0), p.LiftedAtomParameterContext):
        return child.getChild(0).getText()
    return None


def _extractObjectDisequality(clause) -> Tuple[str, str] | None:
    """If clause is (not (= ?x ?y)) with object variables, return (?x, ?y). Else None."""
    if not isinstance(clause, p.NegatedComparationContext):
        return None
    inner = clause.getChild(2)
    if not isinstance(inner, p.ComparationContext):
        return None
    if inner.getChildCount() < 4:
        return None
    op = inner.getChild(1).getText() if inner.getChild(1) else None
    if op != '=':
        return None
    lhs_var = _isObjectVar(inner.getChild(2))
    rhs_var = _isObjectVar(inner.getChild(3))
    if lhs_var is not None and rhs_var is not None:
        return (lhs_var, rhs_var)
    return None


class Formula:
    type: str
    conditions: [Formula or Predicate]
    disequalities: List[Tuple[str, str]]  # object inequality constraints: (?x, ?y) means x != y

    def __init__(self):
        self.type = "AND"
        self.conditions = list()
        self.disequalities = list()

    def __deepcopy__(self, m=None) -> Formula:
        m = {} if m is None else m
        f = Formula()
        f.type = self.type
        f.conditions = copy.deepcopy(self.conditions, m)
        f.disequalities = copy.deepcopy(self.disequalities, m)
        return f

    @classmethod
    def fromNode(cls, node) -> Formula:
        formula = cls()

        if isinstance(node.getChild(0), p.EmptyPreconditionContext):
            return formula

        clauses = []

        formulaComponent = node.getChild(0) if type(node) == p.PreconditionsContext else node
        formula.type = "OR" if type(formulaComponent) == p.OrClauseContext else "AND"
        if isinstance(formulaComponent, p.BooleanLiteralContext):
            clauses.append(formulaComponent)
        elif type(formulaComponent) in {p.ComparationContext, p.NegatedComparationContext}:
            clauses.append(formulaComponent)
        elif type(formulaComponent) in {p.AndClauseContext, p.OrClauseContext}:
            clauses = formulaComponent.children
        else:
            raise Exception("Unexpected clause in precondition")

        for clause in clauses:
            if type(clause) in {p.AndClauseContext, p.OrClauseContext}:
                formula.conditions.append(Formula.fromNode(clause))
            elif isinstance(clause, p.BooleanLiteralContext):
                formula.conditions.append(Literal.fromNode(clause.getChild(0)))
            elif type(clause) in {p.ComparationContext, p.NegatedComparationContext}:
                diseq = _extractObjectDisequality(clause)
                if diseq is not None:
                    formula.disequalities.append(diseq)
                else:
                    formula.conditions.append(BinaryPredicate.fromNode(clause))

        return formula

    @classmethod
    def fromString(cls, string: str) -> Formula:
        return Formula.fromNode(Utilities.getParseTree(string).preconditions())

    def ground(self, subs: Dict[str, str]):
        gFormula = Formula()
        gFormula.type = self.type
        gFormula.disequalities = self.disequalities
        for condition in self.conditions:
            gFormula.conditions.append(condition.ground(subs))
        return gFormula

    def violatesDisequalities(self, subs: Dict[str, str]) -> bool:
        """Return True if any (?x, ?y) disequality is violated (x and y map to the same object)."""
        for (x, y) in self.disequalities:
            if subs.get(x, x) == subs.get(y, y):
                return True
        return False

    def getFunctions(self) -> Set[Atom]:
        functions = set()
        for c in self.conditions:
            if isinstance(c, Literal):
                continue
            functions |= c.getFunctions()
        return functions

    def getPredicates(self):
        return set(chain.from_iterable([c.getPredicates() for c in self.conditions]))

    def substitute(self, subs: Dict[Atom, float], default=None) -> Formula:
        x = Formula()
        x.type = self.type
        x.conditions = [c.substitute(subs, default) for c in self.conditions]
        x.conditions = [c for c in x.conditions if c]
        return x

    def canHappen(self, subs: Dict[Atom, float], default=None) -> bool:
        canHappen = [c.canHappen(subs, default) for c in self.conditions]
        return all(canHappen)

    def replace(self, atom: Atom, w: BinaryPredicate) -> Formula:
        f = Formula()
        f.type = f.type
        for el in self.conditions:
            f.conditions.append(el.replace(atom, w))
        return f

    def __iter__(self):
        return iter(self.conditions)

    def __str__(self):
        return f"({self.type.lower()} {' '.join([str(c) for c in self.conditions])})"

    def __eq__(self, other):
        return str(self) == str(other)

    def __repr__(self):
        return str(self.conditions)

    def __add__(self, other):
        c = Formula()
        c.conditions = self.conditions + other
        return c

    def __len__(self):
        return len(self.conditions)

    def toLatex(self):
        if not self.conditions:
            return r"\emptyset"
        symbol = r"\wedge" if self.type == "AND" else r"\vee"
        return "(" + symbol.join([c.toLatex() for c in self.conditions]) + ")"
        pass

    def containsOrs(self):
        if self.type == "OR":
            return True
        for c in self.conditions:
            if isinstance(c, Formula) and c.containsOrs():
                return True
        return False

    def addClause(self, clause: Formula or Predicate):
        self.conditions.append(clause)
