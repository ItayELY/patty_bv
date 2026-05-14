from pysmt.solvers.cvc5 import CVC5Solver
from pysmt.logics import QF_LIA


class CustomCVC5(CVC5Solver):
    LOGICS = [QF_LIA]

    def __init__(self, environment, logic, **kwargs):
        super().__init__(environment, logic, **kwargs)

        # Inject your option AFTER the solver is created
        self.solver.setOption("solve-int-as-bv", "10")
