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


def _compute_scale_factor(consts):
    scale = 1
    for v in consts:
        d = Fraction(v).limit_denominator(1000).denominator
        scale = _lcm(scale, d)
    return scale


def _effect_consts(domain, problem):
    """Constants from action effects, preconditions, and init (not goal).

    Init assignments are only included when the fluent actually appears in some
    action — fluents that are initialised but never read or written (e.g.
    duration-* cost fields in pathwaysmetric) would otherwise inflate the scale
    factor and make every state variable unnecessarily large in BV.
    """
    consts = []
    for action in domain.actions:
        _collect_consts(action.preconditions, consts)
        for eff in action.effects:
            _collect_consts(eff, consts)
    for assignment in problem.init:
        if not isinstance(assignment, BinaryPredicate) or assignment.getAtom() in domain.functions:
            _collect_consts(assignment, consts)
    return consts


def _compute_max_actions(problem):
    """Maximum action repetitions per step: use the largest initial fluent value so
    that a single-step plan can transfer all resources without needing many bounds."""
    max_val = 50
    for fact in problem.init:
        if isinstance(fact, BinaryPredicate) and fact.operator in ("=", "assign"):
            try:
                v = abs(float(str(fact.rhs)))
                if v > max_val:
                    max_val = int(v) + 1
            except Exception:
                pass
    return max_val


def _compute_min_width(domain, problem, effect_scale, goal_scale, max_actions=1):
    """Compute BV width to hold state values and goal-scaled constants.

    State variables are scaled by effect_scale.  Goal constants (coefficients
    and RHS thresholds) are scaled by goal_scale.  The worst-case BV value is
    the larger of the max goal-scaled constant and the max state value; one
    extra bit is added for intermediate sums.

    Repeatable actions (Operation.couldBeRepeated) are batched into a single
    "repeat count" variable rather than unrolled step-by-step, and their own
    precondition is checked via interval arithmetic: the extrapolated state
    after (count - 1) repetitions is computed as
    ``delta + effect_amount * (count - 1)`` (getPreStepRules/getDeltaStepRules).
    That multiplication is itself a fixed-width BV value - if effect_amount *
    max_actions overflows the chosen width, it silently wraps, and an
    otherwise-impossible repeat count can appear to satisfy a precondition
    purely because the wrapped value happens to land back in range. Budgeting
    for that product (using the largest constant anywhere as a safe upper
    bound on any single effect's magnitude) keeps the interval-arithmetic
    extrapolation sound.
    """
    ec = _effect_consts(domain, problem)
    gc = []
    _collect_consts(problem.goal, gc)

    if not ec and not gc:
        return 15

    max_state = max((abs(Fraction(str(v)) * effect_scale) for v in ec), default=Fraction(1))
    max_goal = max((abs(Fraction(str(v)) * goal_scale) for v in gc), default=Fraction(1))
    max_repeat_delta = max_state * max_actions

    max_val = int(max(max_state, max_goal, max_repeat_delta))
    if max_val < 1:
        return 15

    # +1 for signed bit, +1 safety margin, +1 for intermediate sums in goal
    bits = max_val.bit_length() + 3
    return max(bits, 10)


def to_bv(value, width):
    if value < 0:
        value = (1 << width) + value
    return BV(value, width)


class PDDL2SMTBV:
    domain: GroundedDomain
    problem: Problem

    def __init__(self, domain: GroundedDomain, problem: Problem, pattern: Pattern, bound: int, encoding="non-linear", width=None, max_actions=None,
                 binaryActions=10, rollBound=0, hasEffectAxioms=False):
        self.domain = domain
        self.problem = problem
        self.bound = bound
        self.encoding = encoding
        self.rollBound = rollBound
        self.hasEffectAxioms = hasEffectAxioms
        self.max_actions = max_actions if max_actions is not None else _compute_max_actions(problem)
        ec = _effect_consts(domain, problem)
        gc = []
        _collect_consts(problem.goal, gc)
        # effect_scale: clears denominators in action effects / preconditions / init
        self.effect_scale = _compute_scale_factor(ec)
        # goal_scale: clears denominators across everything including goal coefficients
        self.goal_scale = _compute_scale_factor(ec + gc)
        # Legacy alias used in a few internal paths
        self.scale_factor = self.goal_scale
        max_repeat_count = self.rollBound if self.rollBound else self.max_actions
        self.width = width if width is not None else _compute_min_width(domain, problem, self.effect_scale, self.goal_scale, max_repeat_count)
        # action counts are small (bounded by max_actions); use a narrow BV to keep solver fast
        self.action_width = max(int(self.max_actions + 1).bit_length() + 1, 8)

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
                rules.append(tVars.valueVariables[assignment.getAtom()] == to_bv(round(float(str(assignment.rhs)) * self.effect_scale), self.width))

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
                expr = SMTExpression.fromPddl(condition, tVars.valueVariables, bv=True, width=self.width, scale_factor=self.goal_scale, effect_scale=self.effect_scale)
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
                        k = SMTNumericVariable.fromPddl(funct, stepVars.deltaVariables[prevAction], bv=True, width=self.width, scale_factor=self.effect_scale)
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
                    rules.append(stepVars.valueVariables[atom] >= to_bv(round(interval.lb * self.effect_scale), self.width))
                if interval.ub != float("+inf"):
                    rules.append(stepVars.valueVariables[atom] <= to_bv(round(interval.ub * self.effect_scale), self.width))

        return rules

    def getPreStepRules(self, stepVars: TransitionVariables) -> List[SMTExpression]:
        rules: List[SMTExpression] = []

        for a in self.pattern:
            if a.isFake:
                continue
            # a_n > 0
            lhs0 = stepVars.actionVariables[a] > to_bv(0, self.action_width)
            preconditions0 = None
            # Non-repeatable actions are bounded to count ≤ 1, so count > 1 is always
            # false; skip the BV-multiplication transformed-precondition entirely.
            can_repeat = a.couldBeRepeated() and not a.hasNonSimpleLinearIncrement(self.encoding)
            preconditions1 = None
            for pre in a.preconditions:
                if isinstance(pre, Literal):
                    v = pre.getAtom()
                    d_av = stepVars.deltaVariables[a][v]
                    rhs = d_av if pre.sign == "+" else d_av.NOT()
                    preconditions0 = preconditions0.AND(rhs) if preconditions0 else rhs
                    if can_repeat:
                        preconditions1 = preconditions1.AND(rhs) if preconditions1 else rhs
                    continue

                precondition0 = SMTNumericVariable.fromPddl(pre, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.effect_scale)
                preconditions0 = preconditions0.AND(precondition0) if preconditions0 else precondition0

                if not can_repeat:
                    continue

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
                                  SMTNumericVariable.fromPddl(eff.rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.effect_scale) * \
                                  (self._ext(stepVars.actionVariables[a]) - to_bv(1, self.width))
                    else:
                        subs[v] = stepVars.deltaVariables[a][v] - \
                                  SMTNumericVariable.fromPddl(eff.rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.effect_scale) * \
                                  (self._ext(stepVars.actionVariables[a]) - to_bv(1, self.width))

                for v in stepVars.deltaVariables[a].keys():
                    subs[v] = subs[v] if v in subs else stepVars.deltaVariables[a][v]

                # Transformed precondition
                precondition1 = SMTNumericVariable.fromPddl(pre, subs, bv=True, width=self.width, scale_factor=self.effect_scale)
                preconditions1 = preconditions1.AND(precondition1) if preconditions1 else precondition1

            if preconditions0:
                rules.append(lhs0.implies(preconditions0))

            if preconditions1:
                lhs1 = stepVars.actionVariables[a] > to_bv(1, self.action_width)
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
                    rhs_expr = SMTExpression.fromPddl(rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.effect_scale)
                    rules.append((a_n > to_bv(0, self.action_width)).implies(v_a == rhs_expr))
                    rules.append((a_n == to_bv(0, self.action_width)).implies(v_a == d_a_v))
                    continue
                vl = float(str(rhs.value))
                v2 = round(vl * self.effect_scale)
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
                d_a_phi = SMTNumericVariable.fromPddl(eff.rhs, stepVars.deltaVariables[a], bv=True, width=self.width, scale_factor=self.effect_scale)
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
