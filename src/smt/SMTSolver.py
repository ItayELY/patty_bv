import io
from pysmt.logics import QF_LRA, QF_NRA, QF_LIRA, QF_LIA
from pysmt.shortcuts import Portfolio, get_free_variables, And
from pysmt.smtlib.script import SmtLibScript, SmtLibCommand
from pysmt.typing import INT, REAL
import pysmt.smtlib.commands as smtcmd
from typing import Set, List

from src.pddl.NumericPlan import NumericPlan
from src.plan.PDDL2SMT import PDDL2SMT
from src.smt.SMTExpression import SMTExpression
from src.smt.SMTSolution import SMTSolution
from src.smt.SMTVariable import SMTVariable


class SMTSolver:
    solver: Portfolio
    variables: Set[SMTVariable]

    def __init__(self, pddl2smt: PDDL2SMT = None, solver="z3"):
        self.variables: Set[SMTVariable] = set()
        self.assertions: List[SMTExpression] = list()
        self.pddl2smt: PDDL2SMT = pddl2smt
        # solver = ("cvc5")#, {"solve-int-as-bv": "10"})

        self.solver: Portfolio = Portfolio([solver],
                                           logic=QF_LRA,
                                           incremental=False, # false for cvc5 BV #True,
                                           generate_models=True,)

        if self.pddl2smt:
            self.addAssertions(self.pddl2smt.rules)

    def addAssertion(self, expr: SMTExpression, push=True):
        self.assertions.append(expr)
        self.variables.update(expr.variables)
        self.solver.add_assertion(expr.expression)

        if push:
            self.solver.push()

    def addAssertions(self, exprs: [SMTExpression], push=True):
        for expr in exprs:
            self.addAssertion(expr, push=False)

        if push:
            self.solver.push()

    def popLastAssertion(self):
        self.assertions.pop()
        self.solver.pop()
        self.solver.push()  # I repush to keep the stack with the last actions

    def exit(self):
        self.solver.exit()
        pass

    def _write_smtlib_dump(self, path="smtlib_dump_regular"):
        formulas = [a.expression for a in self.assertions]
        all_vars = set()
        for f in formulas:
            all_vars |= get_free_variables(f)

        types = {v.get_type() for v in all_vars}
        has_int = INT in types
        has_real = REAL in types
        if has_int and has_real:
            logic = QF_LIRA
        elif has_int:
            logic = QF_LIA
        else:
            logic = QF_LRA

        script = SmtLibScript()
        script.add_command(SmtLibCommand(smtcmd.SET_LOGIC, [logic]))
        for var in sorted(all_vars, key=lambda v: v.symbol_name()):
            script.add_command(SmtLibCommand(smtcmd.DECLARE_FUN, [var]))
        for f in formulas:
            script.add_command(SmtLibCommand(smtcmd.ASSERT, [f]))
        script.add_command(SmtLibCommand(smtcmd.CHECK_SAT, []))

        buf = io.StringIO()
        script.serialize(buf)
        with open(path, "w") as f:
            f.write(buf.getvalue())

    def getSolution(self) -> SMTSolution or bool:
        if __import__('os').environ.get('SMTLIB_DUMP'):
            self._write_smtlib_dump()
        found = self.solver.solve()
        if not found:
            return False

        solution = SMTSolution()
        for variable in self.variables:
            value = self.solver.get_value(variable.expression)
            solution.addVariable(variable, value)

        return solution

    def solve(self) -> NumericPlan or bool:

        solution = self.getSolution()
        if not solution:
            return False
        plan = self.pddl2smt.getPlanFromSolution(solution)
        # plan.quality = plan.getMetric(self.pddl2smt.problem)

        return plan

    # Linear Optimization
    def optimize(self) -> NumericPlan or bool:

        lastPlanFound: NumericPlan = self.solve()
        if not lastPlanFound:
            return False

        while True:
            assert lastPlanFound.validate(self.pddl2smt.problem)
            print(f"Found plan with quality {lastPlanFound.quality}. Improving...")
            self.addAssertion(self.pddl2smt.getMetricExpression(lastPlanFound.quality))

            plan = self.solve()
            if not plan or plan.quality == lastPlanFound.quality:
                lastPlanFound.optimal = True
                return lastPlanFound

            lastPlanFound = plan
            self.popLastAssertion()

    def __solveBelowQuality(self, quality: float):
        # print("Searching below", quality)
        self.addAssertion(self.pddl2smt.getMetricExpression(quality), push=False)
        plan = self.solve()
        self.popLastAssertion()
        return plan

    def __searchBetween(self, ub: float, lb: float, error: float, lastPlan: NumericPlan,
                        onSolutionFound=None) -> NumericPlan:
        if abs(ub - lb) < error:
            lastPlan.optimal = True
            return lastPlan

        half = lb + (ub - lb) / 2
        print(f"Searching plan with quality {half}.")
        plan = self.__solveBelowQuality(half)
        if plan and plan.quality != lastPlan.quality:
            print(f"Plan FOUND with quality {plan.quality}.")
            if onSolutionFound:
                onSolutionFound(plan)
            return self.__searchBetween(plan.quality, lb, error, plan, onSolutionFound)
        if not plan or plan.quality == lastPlan.quality:
            print(f"Plan NOT FOUND with quality {half}.")
            return self.__searchBetween(ub, half, error, lastPlan, onSolutionFound)

    def optimizeBinary(self, error=1, onSolutionFound=None) -> NumericPlan or bool:

        lastPlanFound: NumericPlan = self.solve()
        if not lastPlanFound:
            return False
        if onSolutionFound:
            onSolutionFound(lastPlanFound)

        return self.__searchBetween(lastPlanFound.quality, 0, error, lastPlanFound, onSolutionFound)
