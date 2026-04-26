from pysmt.shortcuts import Symbol, BV, Equals
from pysmt.typing import BOOL, BVType
from src.smt.SMTExpression import SMTExpression
from src.smt.SMTVariable import SMTVariable


def toRHS(other, target_type=None):
    """
    Converts a Python constant to a pySMT constant, respecting the target type.
    Crucial for Bit-Vectors to ensure constants match the bit-width.
    """
    if isinstance(other, SMTExpression):
        return other.expression
    
    # If the target is a Bit-Vector, the constant must be a BV of the same width
    if target_type and target_type.is_bv_type():
        # Strip .0 from floats (like 1.0) to get a clean integer
        val = int(float(other)) if isinstance(other, (int, float)) else other
        return BV(val, target_type.width)
        
    if isinstance(other, int) or (isinstance(other, float) and other.is_integer()):
        return Int(int(other))
    if isinstance(other, float):
        return Real(other)
    return other
class SMTBVVariable(SMTVariable):
    def __init__(self, name: str, width: int):
        super().__init__()
        self.width = width
        # CRITICAL: This must be a pySMT Type object for SMTExpression logic to work
        self.type = BVType(width) 
        # self.node_type =  BVType(width) 
        self.expression = Symbol(name, self.type)

    def const(self, value: int):
        """Helper to create a BV constant of matching width."""
        return BV(int(float(value)), self.width)
    def __hash__(self):
        # Hash the underlying pySMT FNode (Symbol)
        # This ensures the variable is unique in sets based on its name (e.g., 'fuel_0')
        return hash(self.expression)

    # def node_type(self):
    #      return self.type

    # def __eq__(self, other):
        # Required for set membership logic
        # if self.type == BOOL: return self.coimplies(other)
        # expr = self.__binary(other, Equals, self.expression, toRHS(other, self.type))
        # try:
                # return self.expression == other.expression
        # except:
            # return self.expression == other
        # if isinstance(other, self.__class__) :
        #     return self.expression == other.expression
        # # If comparing to an SMTExpression or number, fall back to SMT logic
        # return super().__eq__(other)