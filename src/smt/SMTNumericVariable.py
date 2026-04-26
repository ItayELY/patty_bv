from pysmt.shortcuts import Symbol, BV
from pysmt.typing import REAL, INT, BVType

from src.smt.SMTVariable import SMTVariable
BV_WIDTH = 10        # replaces --solve-int-as-bv=10
BV_SIGNED = True     # True = signed, False = unsigned


class SMTNumericVariable(SMTVariable):

    def __init__(self, name: str, varType):
        super().__init__()
        self.expression = Symbol(name, varType)
        self.type = varType

    def __hash__(self):
        return hash(self.expression)


class SMTIntVariable(SMTNumericVariable):
    def __init__(self, name: str):
        super().__init__(name, INT)


class SMTRealVariable(SMTNumericVariable):
    def __init__(self, name: str):
        super().__init__(name, REAL)


class SMTBVVariable(SMTVariable):
    def __init__(self, name: str):
        super().__init__()
        self.expression = Symbol(name, BVType(BV_WIDTH))
        self.type = "BV"

    def const(self, value: int):
        """
        Create a BV constant of the same width.
        """
        return BV(value, self.width)
