from pysmt.shortcuts import Not, BVNot
from src.smt.SMTExpression import SMTExpression
from pysmt.typing import BOOL

class SMTNegation(SMTExpression):
    def __init__(self, expr: SMTExpression):
        super().__init__()
        self.variables = expr.variables
        self.positive = expr
        
        # Determine if we use Logical Not or Bitwise Not
        if expr.type.is_bv_type():
            self.type = expr.type
            self.expression = BVNot(expr.expression)
        else:
            self.type = BOOL
            self.expression = Not(expr.expression)

    def __hash__(self):
        return hash(self.expression)