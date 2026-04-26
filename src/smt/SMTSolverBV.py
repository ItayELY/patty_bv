from typing import List, Set, Union
from pysmt.logics import QF_BV
from pysmt.shortcuts import Portfolio, get_model
from pysmt.typing import BVType

from src.smt.SMTBVVariable import SMTBVVariable
from src.smt.SMTExpression import SMTExpression
from src.smt.SMTSolver import SMTSolver
from src.smt.SMTSolution import SMTSolution
from src.plan.PDDL2SMT import PDDL2SMT

class SMTSolverBV(SMTSolver):
    def __init__(self, pddl2smt: PDDL2SMT = None, solver="z3", width=16):
        """
        :param width: The default bit-width for BV variables (e.g., 16 or 32).
        """
        self.variables: Set[SMTBVVariable] = set()
        self.assertions: List[SMTExpression] = list()
        self.pddl2smt: PDDL2SMT = pddl2smt
        self.width = width # Crucial for BV consistency

        # Initialize the Portfolio solver with Bit-Vector logic
        self.solver: Portfolio = Portfolio([solver],
                                           logic=QF_BV,
                                           incremental=True,
                                           generate_models=True)


        if self.pddl2smt:
            self.addAssertions(self.pddl2smt.rules)

    def getSolution(self) -> SMTSolution or bool:
        found = self.solver.solve()
        if not found:
            return False

        solution = SMTSolution()
        for variable in self.variables:
            val_fnode = self.solver.get_value(variable.expression)
            
            if val_fnode.is_bv_constant():
                # Correctly extracts the Python integer from a bit-vector
                value = val_fnode.constant_value()
            elif val_fnode.is_bool_constant():
                value = val_fnode.is_true()
            else:
                value = val_fnode
                
            solution.addVariable(variable, value)

        return solution
    def addAssertion(self, expr: SMTExpression, push=True):
        """
        Adds an assertion to the BV solver. 
        Note: The PDDL2SMT must ensure expr is built using BV operators.
        """
        if not isinstance(expr, SMTExpression):
            pass
        self.assertions.append(expr)
        self.variables.update(expr.variables)
        
        # Validation: pySMT will throw a PysmtTypeError here if 
        # the expression mixes BV and INT/REAL.
        
        # raise TypeError(
            # f"addAssertion expects SMTExpression, got {type(expr)}"
        # )
        self.solver.add_assertion(expr.expression)

        if push:
            self.solver.push()

    def print_debug_model(self):
        """
        Helper to debug initial states in planning.
        """
        if self.solver.solve():
            print("\n--- BV MODEL DEBUG ---")
            for var in sorted(list(self.variables), key=lambda x: x.expression.symbol_name()):
                val = self.solver.get_value(var.expression)
                print(f"{var.expression.symbol_name()}: {val.constant_value()}")