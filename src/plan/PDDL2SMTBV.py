from fractions import Fraction
from math import gcd as _gcd, log2, ceil
from typing import List, Dict, Set

from pysmt.shortcuts import TRUE, FALSE, BVZExt
from pysmt.typing import BVType

from src.pddl.Action import Action
from src.pddl.Atom import Atom
from src.pddl.BinaryPredicate import BinaryPredicate
from src.pddl.Constant import Constant
from src.pddl.Domain import GroundedDomain
from src.pddl.Formula import Formula
from src.pddl.Literal import Literal
from src.pddl.NumericPlan import NumericPlan
from src.pddl.Problem import Problem
from src.plan.Pattern import Pattern
from src.plan.TransitionVariables import TransitionVariables
from src.plan.TransitionVariablesBV import TransitionVariablesBV
from src.smt.SMTExpression import SMTExpression
from src.smt.SMTNumericVariable import SMTNumericVariable
from src.smt.SMTSolution import SMTSolution
from pysmt.shortcuts import BV
# BOUND = 1000
EXPLICIT_DELTA = False


def _lcm(a, b):
    return a * b // _gcd(a, b)


def _collect_consts(obj, out):
    if isinstance(obj, Constant):
        out.append(obj.value)
    elif isinstance(obj, BinaryPredicate):
        _collect_consts(obj.lhs, out)
        _collect_consts(obj.rhs, out)
    elif isinstance(obj, Formula):
        for c in obj.conditions:
            _collect_consts(c, out)


def _compute_scale_factor(domain, problem):
    consts = []
    for action in domain.actions:
        _collect_consts(action.preconditions, consts)
        for eff in action.effects:
            _collect_consts(eff, consts)
    for assignment in problem.init:
        _collect_consts(assignment, consts)
    scale = 1
    for v in consts:
        d = Fraction(v).limit_denominator(1000).denominator
        scale = _lcm(scale, d)
    return scale


def _compute_min_width(domain, problem, scale_factor):
    consts = []
    for action in domain.actions:
        _collect_consts(action.preconditions, consts)
        for eff in action.effects:
            _collect_consts(eff, consts)
    for assignment in problem.init:
        _collect_consts(assignment, consts)
    _collect_consts(problem.goal, consts)

    if not consts:
        return 15

    max_val = max(abs(Fraction(str(v)) * scale_factor) for v in consts)
    if max_val < 1:
        return 15

    # +1 for signed bit, +1 safety margin
    bits = int(max_val).bit_length() + 2
    return max(bits, 10)


def to_bv(value, width):
    if value < 0:
        value = (1 << width) + value
    return BV(value, width)


class PDDL2SMTBV:
    domain: GroundedDomain
    problem: Problem

    def __init__(self, domain: GroundedDomain, problem: Problem, pattern: Pattern, bound: int, encoding="non-linear", width=None, max_actions=50,
                 binaryActions=10, rollBound=0, hasEffectAxioms=False):
        self.domain = domain
        self.problem = problem
        self.bound = bound
        self.encoding = encoding
        self.rollBound = rollBound
        self.hasEffectAxioms = hasEffectAxioms
        self.max_actions = max_actions
        self.scale_factor = _compute_scale_factor(domain, problem)
        self.width = width if width is not None else _compute_min_width(domain, problem, self.scale_factor)
        # action counts are small (bounded by max_actions); use a narrow BV to keep solver fast
        self.action_width = max(int(max_actions + 1).bit_length() + 1, 8)

        self.transitionVariables: [TransitionVariablesBV] = list()

        self.transitions: [SMTExpression] = []

        self.pattern = pattern
        if self.encoding == "binary":
            self.pattern.extendNonLinearities(binaryActions)

        for index in range(0, bound + 1):
            var = TransitionVariablesBV(self.domain.predicates, self.domain.functions, self.domain.assList, self.pattern,
                                      index, hasEffectAxioms, width=self.width, action_width=self.action_width)
            self.transitionVariables.append(var)

        self.initial: [SMTExpression] = self.getInitialExpression()
        self.goal: [SMTExpression] = self.getGoalExpression()

        for index in range(1, bound + 1):
            stepRules = self.getStepRules(index)
            self.transitions.extend(stepRules)

        # self.rules = self.initial + self.transitions + [self.goal]
        self.rules = self.initial + self.transitions + [self.goal]
        pass

    def _ext(self, a_n: SMTExpression) -> SMTExpression:
        """Zero-extend an action_width BV to value_width for arithmetic with state vars."""
        if self.action_width == self.width:
            return a_n
        ext_expr = BVZExt(a_n.expression, self.width - self.action_width)
        result = SMTExpression()
        result.expression = ext_expr
        result.variables = a_n.variables if hasattr(a_n, 'variables') else set()
        result.type = BVType(self.width)
        return result

    def getInitialExpression(self) -> List[SMTExpression]:
        tVars = self.transitionVariables[0]
        rules: [SMTExpression] = list()

        trueAtoms: Set[Atom] = set()
        for assignment in self.problem.init:
            atom = assignment.getAtom()
            if atom not in tVars.valueVariables:
                # print(f"Atom {atom} in initial condition doesn't concur in achieving the goal. Pruned.")
                continue
            if isinstance(assignment, BinaryPredicate):
                if assignment.getAtom() not in self.domain.allAtoms:
                    # print(f"Atom {assignments.getAtom()} was pruned since it's a constant")
                    continue
                rules.append(tVars.valueVariables[assignment.getAtom()] == to_bv(round(float(str(assignment.rhs)) * self.scale_factor), self.width))

            elif isinstance(assignment, Literal):
                rules.append(tVars.valueVariables[assignment.getAtom()])
                trueAtoms.add(assignment.getAtom())
            else:
                raise NotImplemented("Shouldn't go here")

        for v in self.domain.predicates - trueAtoms:
            rules.append(tVars.valueVariables[v].NOT())

        return rules

    def getGoalRuleFromFormula(self, f: Formula) -> SMTExpression:
        tVars = self.transitionVariables[-1]
        rules: [SMTExpression] = []
        for condition in f.conditions:
            if isinstance(condition, BinaryPredicate):
                # tp = (type(condition.rhs.value))
                # if type(condition.rhs.value) in (int, float):
                    # condition.rhs = BV(int(condition.rhs.value), self.width)
                expr = SMTExpression.fromPddl(condition, tVars.valueVariables, bv=True, width=self.width, scale_factor=self.scale_factor)
                rules.append(expr)
            elif isinstance(condition, Literal):
                if condition.sign == "+":
                    rules.append(tVars.valueVariables[condition.getAtom()])
                else:
                    rules.append(tVars.valueVariables[condition.getAtom()].NOT())
            elif isinstance(condition, Formula):
                rules.append(self.getGoalRuleFromFormula(condition))
            else:
                raise NotImplemented("Shouldn't go here")

        if f.type == "AND":
            return SMTExpression.andOfExpressionsList(rules)
        if f.type == "OR":
            return SMTExpression.orOfExpressionsList(rules)

    def getGoalExpression(self) -> SMTExpression:
        return self.getGoalRuleFromFormula(self.problem.goal)

    def getMetricExpression(self, metricBound: float) -> SMTExpression or None:

        if self.problem.metric:
            return SMTNumericVariable.fromPddl(self.problem.metric,
                                               self.transitionVariables[-1].valueVariables) < metricBound

        if not self.problem.metric:
            sumOfActions = 0
            for stepVar in self.transitionVariables[1:]:
                for action in self.pattern:
                    if action.isFake:
                        continue
                    sumOfActions += stepVar.actionVariables[action] * action.linearizationTimes
            return sumOfActions < metricBound

    def getDeltaStepRules(self, prevVars: TransitionVariables, stepVars: TransitionVariables) -> List[SMTExpression]:
        rules: List[SMTExpression] = []

        prevAction: Action or None = None
        for action in self.pattern:
            if not prevAction:
                # First action in the order copies the value from previous step
                for v in self.domain.allAtoms:
                    if self.hasEffectAxioms:
                        rules.append(stepVars.deltaVariables[action][v] == prevVars.valueVariables[v])
                    else:
                        stepVars.deltaVariables[action][v] = prevVars.valueVariables[v]
                prevAction = action
                continue

            # Case a) Not influenced
            notInfluenced = self.domain.allAtoms - (prevAction.getInfluencedAtoms())
            for v in notInfluenced:
                if self.hasEffectAxioms:
                    rules.append(stepVars.deltaVariables[action][v] == stepVars.deltaVariables[prevAction][v])
                else:
                    stepVars.deltaVariables[action][v] = stepVars.deltaVariables[prevAction][v]

            # Case b) Boolean
            for v in prevAction.getAddList() | prevAction.getDelList():
                d_bv = stepVars.deltaVariables[prevAction][v]
                b_n = stepVars.actionVariables[prevAction]

                if v in prevAction.getAddList():
                    if self.hasEffectAxioms:
                        rules.append(stepVars.deltaVariables[action][v] == d_bv.OR(b_n > to_bv(0, self.action_width)))
                    else:
                        stepVars.deltaVariables[action][v] = d_bv.OR(b_n > to_bv(0, self.action_width))

                if v in prevAction.getDelList():
                    if self.hasEffectAxioms:
                        rules.append(stepVars.deltaVariables[action][v] == d_bv.AND(b_n == to_bv(0, self.action_width)))
                    else:
                        stepVars.deltaVariables[action][v] = d_bv.AND(b_n == to_bv(0, self.action_width))
                
            # Case c) Numeric increases or decreases
            if not prevAction.hasNonSimpleLinearIncrement(self.encoding):
                modifications = [(+1, prevAction.getIncreases()), (-1, prevAction.getDecreases())]
                for sign, modificationDict in modifications:
                    for v, funct in modificationDict.items():

                        d_bv = stepVars.deltaVariables[prevAction][v]
                        k = SMTNumericVariable.fromPddl(funct, stepVars.deltaVariables[prevAction], bv=True, width=self.width, scale_factor=self.scale_factor)
                        b_n = self._ext(stepVars.actionVariables[prevAction])
                        if sign > 0:
                            if self.hasEffectAxioms:
                                rules.append(stepVars.deltaVariables[action][v] == d_bv + (k * b_n))
                            else:
                                stepVars.deltaVariables[action][v] = d_bv + (k * b_n)
                        else:
                            if self.hasEffectAxioms:
                                rules.append(stepVars.deltaVariables[action][v] == d_bv - (k * b_n))
                            else:
                                stepVars.deltaVariables[action][v] = d_bv - (k * b_n)
            # Case d) Numeric assignments
            for v in prevAction.getAssList():
                if self.hasEffectAxioms:
                    rules.append(stepVars.deltaVariables[action][v] == stepVars.auxVariables[prevAction][v])
                else:
                    stepVars.deltaVariables[action][v] = stepVars.auxVariables[prevAction][v]

            if prevAction.hasNonSimpleLinearIncrement(self.encoding):
                for eff in prevAction.effects:
                    if not eff.isLinearIncrement():
                        continue
                    v = eff.getAtom()
                    if self.hasEffectAxioms:
                        rules.append(stepVars.deltaVariables[action][v] == stepVars.auxVariables[prevAction][v])
                    else:
                        stepVars.deltaVariables[action][v] = stepVars.auxVariables[prevAction][v]

            prevAction = action

        return rules
    
    def getActStepRules(self, stepVars: TransitionVariables) -> List[SMTExpression]:
        rules: List[SMTExpression] = []

        for a in self.pattern:
            if a.isFake:
                continue
            a_n = stepVars.actionVariables[a]
            rules.append(a_n >= to_bv(0, self.action_width))
            if not a.couldBeRepeated() or (a.hasNonSimpleLinearIncrement(self.encoding)):
                rules.append(a_n <= to_bv(1, self.action_width))
            else:
                maxReps = self.rollBound if self.rollBound else self.max_actions
                rules.append(a_n <= to_bv(maxReps, self.action_width))

        if len(self.domain.arpg.stateLevels) > 2:
            for (atom, interval) in self.domain.arpg.stateLevels[-1].intervals.items():
                if atom not in stepVars.valueVariables:
                    continue
                if interval.lb != float("-inf"):
                    rules.append(stepVars.valueVariables[atom] >= to_bv(round(interval.lb * self.scale_factor), self.width))
                if interval.ub != float("+inf"):
                    rules.append(stepVars.valueVariables[atom] <= to_bv(round(interval.ub * self.scale_factor), self.width))

        return rules

    def getPreStepRules(self, stepVars: TransitionVariables) -> List[SMTExpression]:
        rules: List[SMTExpression] = []

        for a in self.pattern:
            if a.isFake:
                continue
            # a_n > 0
            lhs0 = stepVars.actionVariables[a] > to_bv(0, self.action_width)
            lhs1 = stepVars.actionVariables[a] > to_bv(1, self.action_width)
            preconditions0 = None
            preconditions1 = None
            for pre in a.preconditions:
                if isinstance(pre, Literal):
                    v = pre.getAtom()
                    d_av = stepVars.deltaVariables[a][v]
                    rhs = d_av if pre.sign == "+" else d_av.NOT()
                    preconditions0 = preconditions0.AND(rhs) if preconditions0 else rhs
                    preconditions1 = preconditions1.AND(rhs) if preconditions1 else rhs
                    continue

                precondition0 = SMTNumericVariable.fromPddl(pre, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.scale_factor)
                preconditions0 = preconditions0.AND(precondition0) if preconditions0 else precondition0

                subs: Dict[Atom, SMTExpression] = dict()
                # Searching for decrease effects
                for eff in a.effects:
                    if not isinstance(eff, BinaryPredicate):
                        continue
                    v = eff.lhs.getAtom()
                    if eff.operator == "assign":
                        subs[v] = stepVars.valueVariables[v]
                        continue
                    if eff.operator == "increase":
                        subs[v] = stepVars.deltaVariables[a][v] + \
                                  SMTNumericVariable.fromPddl(eff.rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.scale_factor) * \
                                  (self._ext(stepVars.actionVariables[a]) - to_bv(1, self.width))
                    else:
                        subs[v] = stepVars.deltaVariables[a][v] - \
                                  SMTNumericVariable.fromPddl(eff.rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.scale_factor) * \
                                  (self._ext(stepVars.actionVariables[a]) - to_bv(1, self.width))

                for v in stepVars.deltaVariables[a].keys():
                    subs[v] = subs[v] if v in subs else stepVars.deltaVariables[a][v]

                # Transformed precondition
                precondition1 = SMTNumericVariable.fromPddl(pre, subs, bv=True, width=self.width, scale_factor=self.scale_factor)
                preconditions1 = preconditions1.AND(precondition1) if preconditions1 else precondition1

            if preconditions0:
                rules.append(lhs0.implies(preconditions0))

            if preconditions1:
                rules.append(lhs1.implies(preconditions1))
        return rules

    def getEffStepRules(self, stepVars: TransitionVariables) -> List[SMTExpression]:
        rules: List[SMTExpression] = []

        for a in self.pattern:
            for var, rhs in a.getAssignments().items():
                v_a = stepVars.auxVariables[a][var]
                a_n = stepVars.actionVariables[a]
                d_a_v = stepVars.deltaVariables[a][var]
                if not isinstance(rhs, Constant):
                    raise Exception("I cannot handle yet linear assignments")
                vl = float(str(rhs.value))
                v2 = round(vl * self.scale_factor)
                k = to_bv(v2, self.width)
                rules.append((a_n > to_bv(0, self.action_width)).implies(v_a == k))
                rules.append((a_n == to_bv(0, self.action_width)).implies(v_a == d_a_v))

            if not a.hasNonSimpleLinearIncrement(self.encoding):
                continue

            for eff in a.effects:
                if not eff.isLinearIncrement():
                    continue
                var = eff.getAtom()
                v_a = stepVars.auxVariables[a][var]
                a_n = stepVars.actionVariables[a]
                d_a_v = stepVars.deltaVariables[a][var]
                d_a_phi = SMTNumericVariable.fromPddl(eff.rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.scale_factor)
                if eff.operator == "increase":
                    rules.append((a_n > to_bv(0, self.action_width)).implies(v_a == d_a_v + d_a_phi))
                else:
                    rules.append((a_n > to_bv(0, self.action_width)).implies(v_a == d_a_v - d_a_phi))
                rules.append((a_n == to_bv(0, self.action_width)).implies(v_a == d_a_v))

        return rules

    def getFrameStepRules(self, stepVars: TransitionVariables) -> List[SMTExpression]:
        rules: List[SMTExpression] = []

        for v in self.domain.functions:
            v_first = stepVars.valueVariables[v]
            delta_g_v = stepVars.deltaVariables[self.pattern.dummyAction][v]
            rules.append(v_first == delta_g_v)

        for v in self.domain.predicates:
            v_first = stepVars.valueVariables[v]
            delta_g_v = stepVars.deltaVariables[self.pattern.dummyAction][v]
            rules.append(delta_g_v.coimplies(v_first))

        return rules


    def getStepRules(self, index: int) -> List[SMTExpression]:
        prevVars = self.transitionVariables[index - 1]
        stepVars = self.transitionVariables[index]

        rules: List[SMTExpression] = []
        rules += self.getDeltaStepRules(prevVars, stepVars)
        rules += self.getActStepRules(stepVars)
        rules += self.getPreStepRules(stepVars)
        rules += self.getEffStepRules(stepVars)
        rules += self.getFrameStepRules(stepVars)

        return rules

    def printRules(self):
        for rule in self.rules:
            print(rule)

    def __str__(self):
        string = ""
        for rule in self.rules:
            string += str(rule) + "\n"
        return string

    def getPlanFromSolution(self, solution: SMTSolution) -> NumericPlan:
        step_plans = []
        

        if not solution:
            return NumericPlan()

        for i in range(1, self.bound + 1):
            plan = NumericPlan()
            stepVar = self.transitionVariables[i]
            for a in self.pattern:
                if a.isFake:
                    continue
                # drive truck0 depot0 market5_1_n

                # drive truck0 depot0 market5_1_n
                val = solution.getVariable(stepVar.actionVariables[a])
                if val is None or val >= 2**(self.action_width - 1):
                    repetitions = 0
                else:
                    repetitions = int(val) * a.linearizationTimes
                if repetitions > 0:
                    plan.addRepeatedAction(a.linearizationOf, repetitions)
            step_plans.append(plan)

        return step_plans

    def getNVars(self):
        variables = set()
        for rule in self.rules:
            variables |= rule.variables
        return len(variables)

    def getNRules(self):
        return len(self.rules)
