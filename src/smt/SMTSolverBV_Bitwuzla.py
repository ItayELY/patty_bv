from typing import Set, List

import pysmt.operators as op
from bitwuzla import TermManager, Bitwuzla, Options, Kind, Result, Option

from src.pddl.NumericPlan import NumericPlan
from src.plan.PDDL2SMT import PDDL2SMT
from src.smt.SMTExpression import SMTExpression
from src.smt.SMTSolution import SMTSolution
from src.smt.SMTVariable import SMTVariable


class _PySMTConverter:
    """Converts pysmt FNodes to bitwuzla Terms."""

    def __init__(self, tm: TermManager):
        self.tm = tm
        self._cache = {}

    def get_bv_sort(self, width: int):
        return self.tm.mk_bv_sort(width)

    def convert(self, fnode):
        fid = fnode.node_id()
        if fid in self._cache:
            return self._cache[fid]

        # Iterative post-order traversal to avoid hitting Python's recursion limit
        # on deeply nested formula trees.
        stack = [(fnode, False)]
        while stack:
            node, children_pushed = stack.pop()
            nid = node.node_id()
            if nid in self._cache:
                continue
            nt = node.node_type()
            if nt in (op.SYMBOL, op.BOOL_CONSTANT, op.BV_CONSTANT):
                self._cache[nid] = self._do_convert(node)
            elif not children_pushed:
                stack.append((node, True))
                for child in node.args():
                    if child.node_id() not in self._cache:
                        stack.append((child, False))
            else:
                self._cache[nid] = self._do_convert(node)

        return self._cache[fid]

    def _do_convert(self, fnode):
        nt = fnode.node_type()
        tm = self.tm

        if nt == op.SYMBOL:
            stype = fnode.symbol_type()
            if stype.is_bool_type():
                sort = tm.mk_bool_sort()
            elif stype.is_bv_type():
                sort = tm.mk_bv_sort(stype.width)
            else:
                raise ValueError(f"Unsupported symbol type: {stype}")
            return tm.mk_const(sort, fnode.symbol_name())

        if nt == op.BOOL_CONSTANT:
            return tm.mk_true() if fnode.constant_value() else tm.mk_false()

        if nt == op.BV_CONSTANT:
            sort = tm.mk_bv_sort(fnode.bv_width())
            return tm.mk_bv_value(sort, fnode.bv_unsigned_value())

        args = [self.convert(a) for a in fnode.args()]

        _unary = {
            op.NOT: Kind.NOT,
            op.BV_NOT: Kind.BV_NOT,
            op.BV_NEG: Kind.BV_NEG,
        }
        if nt in _unary:
            return tm.mk_term(_unary[nt], args)

        _binary = {
            op.IMPLIES: Kind.IMPLIES,
            op.IFF: Kind.IFF,
            op.EQUALS: Kind.EQUAL,
            op.BV_ADD: Kind.BV_ADD,
            op.BV_SUB: Kind.BV_SUB,
            op.BV_MUL: Kind.BV_MUL,
            op.BV_UDIV: Kind.BV_UDIV,
            op.BV_UREM: Kind.BV_UREM,
            op.BV_SDIV: Kind.BV_SDIV,
            op.BV_SREM: Kind.BV_SREM,
            op.BV_ULT: Kind.BV_ULT,
            op.BV_ULE: Kind.BV_ULE,
            op.BV_SLT: Kind.BV_SLT,
            op.BV_SLE: Kind.BV_SLE,
            op.BV_COMP: Kind.BV_COMP,
            op.BV_CONCAT: Kind.BV_CONCAT,
            op.BV_LSHL: Kind.BV_SHL,
            op.BV_LSHR: Kind.BV_SHR,
            op.BV_ASHR: Kind.BV_ASHR,
            op.BV_AND: Kind.BV_AND,
            op.BV_OR: Kind.BV_OR,
            op.BV_XOR: Kind.BV_XOR,
        }
        if nt in _binary:
            return tm.mk_term(_binary[nt], args)

        # n-ary ops
        if nt == op.AND:
            return tm.mk_term(Kind.AND, args)
        if nt == op.OR:
            return tm.mk_term(Kind.OR, args)

        if nt == op.ITE:
            return tm.mk_term(Kind.ITE, args)

        # Indexed ops
        if nt == op.BV_EXTRACT:
            high = fnode.bv_extract_end()
            low = fnode.bv_extract_start()
            return tm.mk_term(Kind.BV_EXTRACT, args, [high, low])

        if nt == op.BV_ZEXT:
            return tm.mk_term(Kind.BV_ZERO_EXTEND, args, [fnode.bv_extend_step()])

        if nt == op.BV_SEXT:
            return tm.mk_term(Kind.BV_SIGN_EXTEND, args, [fnode.bv_extend_step()])

        if nt == op.BV_ROL:
            return tm.mk_term(Kind.BV_ROLI, args, [fnode.bv_rotation_step()])

        if nt == op.BV_ROR:
            return tm.mk_term(Kind.BV_RORI, args, [fnode.bv_rotation_step()])

        raise NotImplementedError(f"Unsupported pysmt op {nt} ({fnode})")


class SMTSolver:
    variables: Set[SMTVariable]

    def __init__(self, pddl2smt: PDDL2SMT = None, solver="bitwuzla"):
        self.variables: Set[SMTVariable] = set()
        self.assertions: List[SMTExpression] = []
        self.pddl2smt: PDDL2SMT = pddl2smt

        opts = Options()
        opts.set(Option.PRODUCE_MODELS, True)

        self._tm = TermManager()
        self._solver = Bitwuzla(self._tm, opts)
        self._conv = _PySMTConverter(self._tm)

        if self.pddl2smt:
            self.addAssertions(self.pddl2smt.rules)

    def addAssertion(self, expr: SMTExpression, push=True):
        self.assertions.append(expr)
        self.variables.update(expr.variables)
        self._solver.assert_formula(self._conv.convert(expr.expression))
        if push:
            self._solver.push()

    def addAssertions(self, exprs: List[SMTExpression], push=True):
        for expr in exprs:
            self.addAssertion(expr, push=False)
        if push:
            self._solver.push()

    def popLastAssertion(self):
        self.assertions.pop()
        self._solver.pop()
        self._solver.push()

    def exit(self):
        pass

    def getSolution(self) -> SMTSolution or bool:
        result = self._solver.check_sat()
        if result != Result.SAT:
            return False

        solution = SMTSolution()
        for variable in self.variables:
            bz_term = self._conv.convert(variable.expression)
            val_term = self._solver.get_value(bz_term)
            bz_sort = bz_term.sort()
            if bz_sort.is_bv():
                solution.addVariable(variable, int(val_term.value(10)))
            elif bz_sort.is_bool():
                solution.addVariable(variable, val_term.value())
            else:
                raise RuntimeError(f"Unhandled sort for variable {variable}")
        return solution

    def solve(self) -> NumericPlan or bool:
        solution = self.getSolution()
        if not solution:
            return False
        return self.pddl2smt.getPlanFromSolution(solution)

    def optimize(self) -> NumericPlan or bool:
        lastPlanFound = self.solve()
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
        self.addAssertion(self.pddl2smt.getMetricExpression(quality), push=False)
        plan = self.solve()
        self.popLastAssertion()
        return plan

    def __searchBetween(self, ub, lb, error, lastPlan, onSolutionFound=None):
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
        print(f"Plan NOT FOUND with quality {half}.")
        return self.__searchBetween(ub, half, error, lastPlan, onSolutionFound)

    def optimizeBinary(self, error=1, onSolutionFound=None) -> NumericPlan or bool:
        lastPlanFound = self.solve()
        if not lastPlanFound:
            return False
        if onSolutionFound:
            onSolutionFound(lastPlanFound)
        return self.__searchBetween(lastPlanFound.quality, 0, error, lastPlanFound, onSolutionFound)
