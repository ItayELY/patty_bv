import time
import unittest
from unittest import TestCase

from src.pddl.Domain import Domain, GroundedDomain
from src.pddl.NumericPlan import NumericPlan
from src.pddl.Problem import Problem
from src.plan.PDDL2SMTBV import PDDL2SMTBV
from src.plan.PatternBV import Pattern
from src.smt.SMTSolverBV_Bitwuzla import SMTSolver


class TestHydropowerBV(TestCase):
    """
    Regression tests for PATTY-BV on the hydropower domain.

    The hydropower domain uses a lookup-table fluent value(n_i) that is
    substituted as a concrete constant during grounding, so the BV encoding
    contains no variable×variable BVMul.  The main cost is the delta-accumulation
    for funds (a 1,000+ node BV expression), which Bitwuzla handles in ~20–30s.
    """

    def _solve(self, problem_file: str, max_bound: int = 3):
        domain = Domain.fromFile("../../files/ipc-2023/hydropower/domain.pddl")
        problem = Problem.fromFile(problem_file)
        gDomain: GroundedDomain = domain.ground(problem)
        pattern = Pattern.fromOrder(gDomain.arpg.getActionsOrder())

        for b in range(1, max_bound + 1):
            pddl2smt = PDDL2SMTBV(
                domain=gDomain,
                problem=problem,
                pattern=pattern,
                bound=b,
            )
            solver = SMTSolver(pddl2smt)
            plan: NumericPlan = solver.solve()
            solver.exit()
            if plan:
                return plan, b, pddl2smt
        return None, -1, None

    def test_no_quadratic_bvmul(self):
        """Hydropower must produce no variable×variable BVMul in its encoding."""
        from pysmt.operators import BV_MUL
        from pysmt.fnode import FNode

        domain = Domain.fromFile("../../files/ipc-2023/hydropower/domain.pddl")
        problem = Problem.fromFile("../../files/ipc-2023/hydropower/instances/pfile02.pddl")
        gDomain: GroundedDomain = domain.ground(problem)
        pattern = Pattern.fromOrder(gDomain.arpg.getActionsOrder())
        pddl2smt = PDDL2SMTBV(domain=gDomain, problem=problem, pattern=pattern, bound=1)

        def has_var_var_bvmul(node: FNode, visited: set) -> bool:
            if id(node) in visited:
                return False
            visited.add(id(node))
            if node.node_type == BV_MUL:
                lhs, rhs = node.args()
                if not lhs.is_bv_constant() and not rhs.is_bv_constant():
                    return True
            return any(has_var_var_bvmul(child, visited) for child in node.args())

        visited: set = set()
        for rule in pddl2smt.transitions:
            self.assertFalse(
                has_var_var_bvmul(rule.expression, visited),
                "Found variable×variable BVMul — grounding should have substituted all value(n_i) constants"
            )

    def test_solve_pfile02(self):
        """pfile02 must be solvable at bound=1 with Bitwuzla."""
        tic = time.perf_counter()
        plan, bound, pddl2smt = self._solve(
            "../../files/ipc-2023/hydropower/instances/pfile02.pddl"
        )
        elapsed = time.perf_counter() - tic

        self.assertIsNotNone(plan, "Expected a valid plan for hydropower pfile02")
        print(f"pfile02 solved at bound={bound} in {elapsed:.2f}s "
              f"(vars={pddl2smt.getNVars()}, rules={pddl2smt.getNRules()})")


if __name__ == "__main__":
    unittest.main()
