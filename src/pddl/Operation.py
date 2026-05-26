from __future__ import annotations

import copy

import itertools
from typing import Dict, List, Set

from src.pddl.Atom import Atom
from src.pddl.BinaryPredicate import BinaryPredicate, BinaryPredicateType
from src.pddl.Effects import Effects
from src.pddl.Literal import Literal
from src.pddl.OperationType import OperationType
from src.pddl.Parameter import Parameter
from src.pddl.Preconditions import Preconditions
from src.pddl.Predicate import Predicate
from src.pddl.Problem import Problem
from src.pddl.Type import Type
from src.pddl.grammar.pddlParser import pddlParser as p


class Operation:
    name: str
    valName: str
    planName: str
    parameters: List[Parameter]
    preconditions: Preconditions
    effects: Effects

    def __init__(self):
        self.name: str = ""
        self.valName: str = ""
        self.parameters = list()
        self.preconditions = Preconditions()
        self.effects = Effects()
        self.functions = set()
        self.predicates = set()
        self.preB = set()
        self.addList = set()
        self.delList = set()
        self.assList = set()
        self.incrList = set()
        self.decrList = set()
        self.influencedAtoms = set()
        self.increases = dict()
        self.decreases = dict()
        self.assignments = dict()
        self.linearizationOf = self
        self.linearizationTimes = 1

    def __deepcopy__(self, m=None) -> Operation:
        m = {} if m is None else m

        a = Operation()
        a.name = self.name
        a.valName = self.valName
        a.parameters = copy.deepcopy(self.parameters, m)
        a.preconditions = copy.deepcopy(self.preconditions, m)
        a.effects = copy.deepcopy(self.effects, m)
        a.functions = copy.deepcopy(self.functions, m)
        a.predicates = copy.deepcopy(self.predicates, m)
        a.preB = copy.deepcopy(self.preB, m)
        a.addList = copy.deepcopy(self.addList, m)
        a.delList = copy.deepcopy(self.delList, m)
        a.assList = copy.deepcopy(self.assList, m)
        a.incrList = copy.deepcopy(self.incrList, m)
        a.decrList = copy.deepcopy(self.decrList, m)
        a.influencedAtoms = copy.deepcopy(self.influencedAtoms, m)
        a.increases = copy.deepcopy(self.increases, m)
        a.decreases = copy.deepcopy(self.decreases, m)
        a.assignments = copy.deepcopy(self.assignments, m)
        a.linearizationOf = self.linearizationOf
        a.linearizationTimes = self.linearizationTimes

        return a

    @classmethod
    def fromNode(cls, node: p.ActionContext or p.EventContext or p.ProcessContext, types: Dict[str, Type]):
        operation = cls()
        for child in node.children:
            if isinstance(child, p.OpNameContext):
                operation.name = child.getText()
            elif isinstance(child, p.OpParametersContext):
                operation.__setParameters(child.getChild(1), types)
            elif isinstance(child, p.OpPreconditionContext):
                operation.__addPreconditions(child)
            elif isinstance(child, p.OpEffectContext):
                operation.__addEffects(child)

        operation.__cacheLists()
        return operation

    @classmethod
    def fromProperties(cls, name: str, preconditions: Preconditions, effects: Effects, planName: str):
        operation = cls()
        operation.name = name
        operation.preconditions = preconditions
        operation.effects = effects
        operation.planName = planName
        operation.__cacheLists()
        return operation

    def __setParameters(self, node: p.ParametersContext, types: Dict[str, Type]):
        for child in node.children:
            if not isinstance(child, p.TypedAtomParameterContext):
                continue
            varNames = []
            try:
                varType = types[child.atomsType.getText()]
            except: continue
            for x in child.children:
                if isinstance(x, p.LiftedAtomParameterContext):
                    varNames.append(x.getText())

            for name in varNames:
                self.parameters.append(Parameter(name, varType))

    def __addPreconditions(self, node: p.OpPreconditionContext):
        self.preconditions = Preconditions.fromNode(node.getChild(1))

    def __addEffects(self, node: p.OpEffectContext):
        self.effects = Effects.fromNode(node.getChild(1))

    def getCombinations(self, problem: Problem):
        subs: List[List[str]] = list()
        for parameter in self.parameters:
            pSubs = list()
            for childType in parameter.type.getMeAndMyChildren():
                if childType.name not in problem.objectsByType:
                    continue
                pSubs += problem.objectsByType[childType.name]
            subs.append(pSubs)

        for sub in itertools.product(*subs):
            yield {parameter.name: sub[i] for i, parameter in enumerate(self.parameters)}

    @staticmethod
    def _iterAndLiterals(formula):
        """Yield Literals from AND-context preconditions only (not inside ORs)."""
        if hasattr(formula, 'type') and formula.type == "OR":
            return
        for c in formula.conditions:
            if isinstance(c, Literal):
                yield c
            elif hasattr(c, 'conditions'):
                yield from Operation._iterAndLiterals(c)

    @staticmethod
    def _constrainedCombinations(parameters, problem, initPredicates, dynamicPredicateNames, preconditions):
        """Generate substitution dicts, pruning via static-predicate constraints.

        Reorders parameters so variables shared with static preconditions are
        bound earliest (topological sort on argument-position dependencies), then
        uses a prefix index over init facts to reduce each variable's domain at
        each recursive step.  For domains with no static constraints this falls
        back to the original Cartesian product.
        """
        from collections import defaultdict

        # Index: (pred_name, position, prefix_tuple) -> set of valid values at that position
        prefix_index = defaultdict(set)
        for atom in initPredicates:
            if atom.name not in dynamicPredicateNames:
                attrs = atom.attributes
                for i in range(len(attrs)):
                    prefix_index[(atom.name, i, tuple(attrs[:i]))].add(attrs[i])

        # Static positive-literal preconditions only
        param_set = {p.name for p in parameters}
        static_lits = [
            (lit.atom.name, lit.atom.attributes)
            for lit in Operation._iterAndLiterals(preconditions)
            if lit.sign == "+" and lit.atom.name not in dynamicPredicateNames
        ]

        # Topological sort: if var_i appears before var_j in a static predicate,
        # var_i should be bound first.
        must_precede = {name: set() for name in param_set}  # must_precede[x] = vars that must come before x
        for (_pred, attrs) in static_lits:
            var_pos = [(i, a) for i, a in enumerate(attrs) if a in param_set]
            for k in range(len(var_pos)):
                for l in range(k + 1, len(var_pos)):
                    must_precede[var_pos[l][1]].add(var_pos[k][1])

        orig_order = {p.name: i for i, p in enumerate(parameters)}
        in_degree = {name: len(must_precede[name]) for name in param_set}
        ready = sorted([n for n in param_set if in_degree[n] == 0], key=lambda x: orig_order[x])
        sorted_names = []
        while ready:
            chosen = ready.pop(0)
            sorted_names.append(chosen)
            for name in param_set:
                if chosen in must_precede[name]:
                    must_precede[name].discard(chosen)
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        ready.append(name)
                        ready.sort(key=lambda x: orig_order[x])
        if len(sorted_names) != len(parameters):
            sorted_names = [p.name for p in parameters]

        # Full type domain per parameter
        full_domain = {}
        for p in parameters:
            d = []
            for childType in p.type.getMeAndMyChildren():
                if childType.name in problem.objectsByType:
                    d += problem.objectsByType[childType.name]
            full_domain[p.name] = d

        def get_domain(name, partial):
            domain = set(full_domain[name])
            for (pred_name, attrs) in static_lits:
                for i, attr in enumerate(attrs):
                    if attr == name:
                        prefix = []
                        ok = True
                        for j in range(i):
                            a = attrs[j]
                            if a in param_set:
                                if a not in partial:
                                    ok = False
                                    break
                                prefix.append(partial[a])
                            else:
                                prefix.append(a)
                        if ok:
                            valid = prefix_index.get((pred_name, i, tuple(prefix)))
                            if valid is not None:
                                domain &= valid
            return domain

        def generate(idx, partial):
            if idx == len(sorted_names):
                yield dict(partial)
                return
            name = sorted_names[idx]
            for val in get_domain(name, partial):
                partial[name] = val
                yield from generate(idx + 1, partial)
            partial.pop(name, None)

        yield from generate(0, {})

    def getGroundedOperations(self, problem, initPredicates=None, dynamicPredicateNames=None):
        if initPredicates is not None and dynamicPredicateNames is not None:
            combinations = Operation._constrainedCombinations(
                self.parameters, problem, initPredicates, dynamicPredicateNames, self.preconditions)
        else:
            combinations = self.getCombinations(problem)
        gOperations = []
        for subs in combinations:
            if self.preconditions.violatesDisequalities(subs):
                continue
            name = self.__getGroundedName(subs)
            preconditions = self.preconditions.ground(subs)
            effects = self.effects.ground(subs)
            planName = self.__getGroundedPlanName(subs)
            operation: Operation = Operation.fromProperties(name, preconditions, effects, planName)
            gOperations.append(operation)
        return gOperations

    def __getGroundedName(self, sub: Dict[str, str]) -> str:
        parts = [self.name] + [c[1] for c in sub.items()]
        return " ".join(parts)

    def __getGroundedPlanName(self, sub: Dict[str, str]):
        parts = [self.name] + [c[1] for c in sub.items()]
        return f"({'_'.join(parts)})"

    @property
    def type(self) -> OperationType:
        raise NotImplemented()

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self)

    def __getFunctions(self) -> Set[Atom]:
        return self.preconditions.getFunctions() | self.effects.getFunctions()

    def __getPredicates(self) -> Set[Atom]:
        return self.preconditions.getPredicates() | self.effects.getPredicates()

    def __getModifiedPredicates(self, sign: str = None) -> Set[Atom]:
        atomList: Set[Atom] = set()
        for c in self.effects:
            if not isinstance(c, Literal) or (sign is not None and c.sign != sign):
                continue
            atomList = atomList | c.getPredicates()
        return atomList

    def __getPreconditionAtoms(self, preconditionClass) -> Set[Atom]:
        atomList: Set[Atom] = set()
        for c in self.preconditions:
            if not isinstance(c, preconditionClass):
                continue
            atomList = atomList | {c.getAtom()}
        return atomList

    def __getModifiedFunctions(self, operator: str = None) -> Set[Atom]:
        atomList: Set[Atom] = set()
        for c in self.effects:
            if not isinstance(c, BinaryPredicate) or (operator is not None and c.operator != operator):
                continue
            atomList = atomList | {c.getAtom()}
        return atomList

    def __getModificationOperations(self, operator: str = None) -> Dict[Atom, Predicate]:
        modification = dict()
        for c in self.effects:
            if not isinstance(c, BinaryPredicate) or (operator is not None and c.operator != operator):
                continue
            modification[c.getAtom()] = c.rhs
        return modification

    def __getPreB(self) -> Set[Atom]:
        return self.__getPreconditionAtoms(Literal)

    def __getAddList(self) -> Set[Atom]:
        return self.__getModifiedPredicates("+")

    def __getDelList(self) -> Set[Atom]:
        return self.__getModifiedPredicates("-")

    def __getAssList(self) -> Set[Atom]:
        return self.__getModifiedFunctions("assign")

    def __getIncrList(self) -> Set[Atom]:
        return self.__getModifiedFunctions("increase")

    def __getDecrList(self) -> Set[Atom]:
        return self.__getModifiedFunctions("decrease")

    def __getInfluencedAtoms(self):
        return self.__getModifiedPredicates() | self.__getModifiedFunctions()

    def __getIncreases(self) -> Dict[Atom, Predicate]:
        return self.__getModificationOperations("increase")

    def __getDecreases(self) -> Dict[Atom, Predicate]:
        return self.__getModificationOperations("decrease")

    def __getAssignments(self) -> Dict[Atom, Predicate]:
        return self.__getModificationOperations("assign")

    def getFunctions(self) -> Set[Atom]:
        return self.functions

    def getPredicates(self) -> Set[Atom]:
        return self.predicates

    def getPreB(self) -> Set[Atom]:
        return self.preB

    def getAddList(self) -> Set[Atom]:
        return self.addList

    def getDelList(self) -> Set[Atom]:
        return self.delList

    def getAssList(self) -> Set[Atom]:
        return self.assList

    def getIncrList(self) -> Set[Atom]:
        return self.incrList

    def getDecrList(self) -> Set[Atom]:
        return self.decrList

    def getInfluencedAtoms(self):
        return self.influencedAtoms

    def getIncreases(self) -> Dict[Atom, Predicate]:
        return self.increases

    def getDecreases(self) -> Dict[Atom, Predicate]:
        return self.decreases

    def getAssignments(self) -> Dict[Atom, Predicate]:
        return self.assignments

    def couldBeRepeated(self) -> bool:
        return len(self.getIncrList() | self.getDecrList()) > 0 and \
            len(self.getPreB().intersection(self.getAddList() | self.getDelList())) == 0

    def substitute(self, sub: Dict[Atom, float], default=None) -> Operation:
        raise NotImplemented()

    def __cacheLists(self):
        self.functions = self.__getFunctions()
        self.predicates = self.__getPredicates()
        self.preB = self.__getPreB()
        self.addList = self.__getAddList()
        self.delList = self.__getDelList()
        self.assList = self.__getAssList()
        self.incrList = self.__getIncrList()
        self.decrList = self.__getDecrList()
        self.influencedAtoms = self.__getInfluencedAtoms()
        self.increases = self.__getIncreases()
        self.decreases = self.__getDecreases()
        self.assignments = self.__getAssignments()

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: Operation):
        if not isinstance(other, Operation):
            return False
        return self.name == other.name

    def nameToLatex(self):
        return self.planName.replace("_", r"\_")

    def hasNonSimpleLinearIncrement(self, encoding=""):
        if encoding == "non-linear":
            return False
        for e in self.effects:
            if isinstance(e, BinaryPredicate) and e.type == BinaryPredicateType.MODIFICATION and \
                    len(e.rhs.getFunctions()) > 0:
                return True
        return False

    def getBinaryOperation(self, i: int) -> Operation:
        o_i = copy.deepcopy(self)

        replaceWith: Dict[Atom, BinaryPredicate] = dict()
        replaceWithSign: Dict[Atom, int] = dict()

        effs = Effects()

        for eff in self.effects:
            if not isinstance(eff, BinaryPredicate) or not eff.isLinearIncrement():
                effs.addEffect(copy.deepcopy(eff))
                continue
            binEff = copy.deepcopy(eff)
            binEff.rhs = 2 ** i * binEff.rhs
            preFormula = (2 ** i - 1) * copy.deepcopy(eff.rhs)
            replaceWith[eff.getAtom()] = preFormula
            replaceWithSign[eff.getAtom()] = +1 if eff.operator == "increase" else -1
            effs.addEffect(binEff)

        o_i.effects = effs

        if self.preconditions.containsOrs():
            raise Exception("""At the moment I cannot deal with ORs in preconditions when linearizing linear effects. 
                Is trivial but requires some work. Please contact us.""")

        for pre in self.preconditions:
            toChange = set(replaceWith.keys()).intersection(pre.getFunctions())
            for v in toChange:
                vl = Literal.fromAtom(v, "+")
                formula = vl + replaceWith[v] if replaceWithSign[v] > 0 else vl - replaceWith[v]
                o_i.preconditions.addClause(pre.replace(v, formula))

        o_i.name = f"{o_i.name}_{2 ** i}"
        return o_i
