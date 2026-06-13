from __future__ import annotations
from fractions import Fraction
from typing import Set, Dict

from pysmt.fnode import FNode
from pysmt.shortcuts import (
    And, Or, Equals, LE, LT, GE, GT, Implies, Real, Times, Minus, Plus, Div,
    TRUE, ToReal, Int, NotEquals, Iff, BV, Not,
    BVAdd, BVSub, BVMul, BVULT, BVULE, BVUGT, BVUGE, BVUGT, Ite, BVSGE, BVSLE, BVSGT, BVSLT,
    BVLShl, BVUDiv
)
from pysmt.typing import REAL, INT, BOOL, BVType

from src.pddl.Atom import Atom
from src.pddl.BinaryPredicate import BinaryPredicate
from src.pddl.Constant import Constant
from src.pddl.Literal import Literal
def to_bv(value, width):
    if value < 0:
        value = (1 << width) + value
    return BV(value, width)


def _bv_const_mul(x_fnode, k, width):
    """Multiply BV FNode x by integer constant k using shifts+adds — no BVMul."""
    k = int(k)
    if k == 0:
        return BV(0, width)
    if k == 1:
        return x_fnode
    result = None
    shift = 0
    remaining = k
    while remaining:
        if remaining & 1:
            term = BVLShl(x_fnode, BV(shift, width)) if shift > 0 else x_fnode
            result = BVAdd(result, term) if result is not None else term
        remaining >>= 1
        shift += 1
    return result

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
        try:
            return val
        except: 
            pass
    if isinstance(other, int) or (isinstance(other, float) and other.is_integer()):
        return Int(int(other))
    if isinstance(other, float):
        return Real(other)
    return other


def getVars(obj):
    # 1. Handle None or primitives
    if obj is None or isinstance(obj, (int, float, bool, str)):
        return set()

    # 2. Handle Lists/Tuples (common in PDDL effects)
    if isinstance(obj, (list, tuple)):
        combined = set()
        for item in obj:
            combined |= getVars(item)
        return combined

    # 3. Check class name for our wrappers
    clazz = obj.__class__.__name__
    
    # If it's a leaf variable (SMTBVVariable, SMTBoolVariable, SMTNumericVariable)
    if "Variable" in clazz:
        return {obj}

    # If it's a compound expression, return the already collected variables
    if clazz == "SMTExpression":
        if hasattr(obj, 'variables') and obj.variables:
            return obj.variables
        # If it has no variables list, it might be a raw wrapper; check lhs/rhs
        vars_found = set()
        if hasattr(obj, 'lhs'): vars_found |= getVars(obj.lhs)
        if hasattr(obj, 'rhs'): vars_found |= getVars(obj.rhs)
        return vars_found

    if clazz == "SMTNegation":
        if hasattr(obj, 'positive'):
            return getVars(obj.positive)
        return set()

    # 4. If it's a pySMT FNode, it has no metadata
    return set()

class SMTExpression:
    expression: FNode
    variables: Set
    lhs: SMTExpression
    rhs: SMTExpression

    def __init__(self):
        self.variables = set()
        self.type = REAL
        self.lhs: SMTExpression
        self.rhs: SMTExpression
        self.expression = TRUE()

    def __str__(self):
        return str(self.expression.serialize())

    def __repr__(self):
        return str(self)
    def ensure_bv(self, value):
        from pysmt.shortcuts import BV
        if isinstance(value, (int, float)):
        # Convert standard numbers to Bit-Vector nodes
            return to_bv(int(value), self.width) # Ensure self.width is accessible
        return value

    def __binary(self, other: SMTExpression or float, operation, lhsExpression: FNode,
                 rhsExpression: FNode) -> SMTExpression:
        # Unwrap SMTExpression wrappers to raw FNodes
        lhs_raw = lhsExpression.expression if hasattr(lhsExpression, 'expression') else lhsExpression
        rhs_raw = rhsExpression.expression if hasattr(rhsExpression, 'expression') else rhsExpression

        from pysmt.environment import get_env
        stc = get_env().stc
        l_type = stc.get_type(lhs_raw)
        try:
            r_type = stc.get_type(rhs_raw)
        except Exception:
            r_type = l_type

        combined_vars = getVars(self) | getVars(other)
        is_bv = (l_type and l_type.is_bv_type()) or (r_type and r_type.is_bv_type())

        if is_bv:
            target_bv_type = l_type if (l_type and l_type.is_bv_type()) else r_type
            width = target_bv_type.width

            # Coerce mismatched widths: convert the non-BV side to a BV constant
            if l_type != r_type:
                if not (l_type and l_type.is_bv_type()):
                    lhs_raw = to_bv(int(float(lhs_raw.constant_value())), width)
                else:
                    rhs_raw = to_bv(int(float(rhs_raw.constant_value())), width)

            bv_map = {
                Plus: BVAdd, Minus: BVSub, Times: BVMul,
                LT: BVSLT, LE: BVSLE, GT: BVSGT, GE: BVSGE,
                Equals: Equals, NotEquals: lambda l, r: Not(Equals(l, r))
            }
            actual_op = bv_map.get(operation, operation)

            expr = SMTExpression()
            expr.variables = combined_vars
            expr.type = target_bv_type

            if actual_op == BVMul:
                # Use shift+add decomposition when one side is a constant — avoids
                # nonlinear BVMul which is extremely slow to bit-blast.
                if rhs_raw.is_bv_constant():
                    expr.expression = _bv_const_mul(lhs_raw, rhs_raw.bv_unsigned_value(), width)
                elif lhs_raw.is_bv_constant():
                    expr.expression = _bv_const_mul(rhs_raw, lhs_raw.bv_unsigned_value(), width)
                else:
                    expr.expression = BVMul(lhs_raw, rhs_raw)
                return expr

            if actual_op == BVSub:
                rhs_const = rhs_raw.is_bv_constant()
                lhs_const = lhs_raw.is_bv_constant()
                if rhs_const and rhs_raw.bv_unsigned_value() == 0:
                    expr.expression = lhs_raw
                else:
                    expr.expression = BVSub(lhs_raw, rhs_raw)
                return expr

            expr.expression = actual_op(lhs_raw, rhs_raw)
            return expr

        # INTEGER/REAL FALLBACK
        if l_type == REAL and r_type == INT:
            rhs_raw = ToReal(rhs_raw)
        elif l_type == INT and r_type == REAL:
            lhs_raw = ToReal(lhs_raw)

        expr = SMTExpression()
        expr.variables = combined_vars
        expr.type = l_type if l_type == r_type else REAL
        expr.expression = operation(lhs_raw, rhs_raw)
        return expr
    # --- Logical Operators ---
    def AND(self, other: SMTExpression):
        other_expr = other.expression if hasattr(other, 'expression') else other
        return self.__binary(other, And, self.expression, other_expr)

    def OR(self, other: SMTExpression):
        other_expr = other.expression if hasattr(other, 'expression') else other
        return self.__binary(other, Or, self.expression, other_expr)

    def NOT(self):
        from src.smt.SMTNegation import SMTNegation
        return SMTNegation(self)

    # --- Comparison Operators ---
    def __eq__(self, other: SMTExpression or int):
        if self.type == BOOL: return self.coimplies(other)
        expr = self.__binary(other, Equals, self.expression, toRHS(other, self.type))
        # expr.type = BOOL
        return expr

    def __ne__(self, other: SMTExpression or int):
        expr = self.__binary(other, NotEquals, self.expression, toRHS(other, self.type))
        # expr.type = BOOL
        return expr

    def __le__(self, other: SMTExpression or float):
        expr = self.__binary(other, LE, self.expression, toRHS(other, self.type))
        # expr.type = BOOL
        return expr

    def __lt__(self, other: SMTExpression or float):
        expr = self.__binary(other, LT, self.expression, toRHS(other, self.type))
        # expr.type = BOOL
        return expr

    def __ge__(self, other: SMTExpression or float):
        expr = self.__binary(other, GE, self.expression, toRHS(other, self.type))
        # expr.type = BOOL
        return expr

    def __gt__(self, other: SMTExpression or float):
        expr = self.__binary(other, GT, self.expression, toRHS(other, self.type))
        # expr.type = BOOL
        return expr

    # --- Arithmetic Operators ---
    def __sub__(self, other: SMTExpression or float):
        return self.__binary(other, Minus, self.expression, toRHS(other, self.type))

    def __rsub__(self, other: SMTExpression or float):
        return self.__binary(other, Minus, toRHS(other, self.type), self.expression)

    def __add__(self, other: SMTExpression or float):
        return self.__binary(other, Plus, self.expression, toRHS(other, self.type))

    def __radd__(self, other: SMTExpression or float):
        return self.__binary(other, Plus, toRHS(other, self.type), self.expression)

    def __mul__(self, other: SMTExpression or float or int):
    # Ensure 'other' is converted to the same SMT type as 'self'
        rhs_expression = toRHS(other, self.type) 
        return self.__binary(other, Times, self.expression, rhs_expression)

    def __rmul__(self, other: SMTExpression or float or int):
    # This is where '1 * expression' is failing
        lhs_expression = toRHS(other, self.type) 

    # DEBUG START
        # print(f"DEBUG: Multiplying {other} (Python Type: {type(other)})")
        # print(f"DEBUG: LHS pySMT type: {lhs_expression.get_type()}")
        # print(f"DEBUG: RHS pySMT type: {self.expression.get_type()}")
    # DEBUG END
        return self.__binary(other, Times, lhs_expression, self.expression)

    def __truediv__(self, other: SMTExpression or float):
        return self.__binary(other, Div, self.expression, toRHS(other, self.type))

    def __rtruediv__(self, other: SMTExpression or float):
        return self.__binary(other, Div, toRHS(other, self.type), self.expression)

    # --- Implication Operators ---
    def implies(self, other: SMTExpression):
        other_expr = other.expression if hasattr(other, 'expression') else other

        expr = self.__binary(other, Implies, self.expression, other_expr)
        # expr.type = BOOL
        return expr

    def coimplies(self, other: SMTExpression):
        expr = self.__binary(other, Iff, self.expression, other.expression)
        # expr.type = BOOL
        return expr

    def impliedBy(self, other: SMTExpression):
        expr = self.__binary(other, Implies, other.expression, self.expression)
        # expr.type = BOOL
        return expr

    @staticmethod
    def opByString(op: str, left: SMTExpression or float, right: SMTExpression or float):
        # Force them to be wrappers if they aren't already
        if not isinstance(left, SMTExpression):
            # This is dangerous; we need to know the type to wrap correctly
            # For now, we trust the __add__ / __sub__ logic we wrote earlier
            pass 

        if op == "and": return left.AND(right)
        if op == "or": return left.OR(right)
        
        # Using the overloaded operators (+, -, *, /) ensures 
        # the __binary method we fixed earlier is called.
        if op == "+": return left + right
        if op == "-": return left - right
        if op == "*": return left * right
        if op == "/": return left / right
        
        if op == ">=": return left >= right
        if op == "<=": return left <= right
        if op == ">": return left > right
        if op == "<": return left < right
        if op == "=": return left == right
        if op == "!=": return left != right

    @classmethod
    def fromPddl(cls, predicate: BinaryPredicate or Literal or Constant,
                 variables: Dict[Atom, SMTExpression], bv=False, width = 0, scale_factor=1,
                 effect_scale=None) -> SMTExpression or float:
        if isinstance(predicate, BinaryPredicate):
            if bv and predicate.operator == "*" and scale_factor > 1:
                lhs_is_const = isinstance(predicate.lhs, Constant)
                rhs_is_const = isinstance(predicate.rhs, Constant)
                if lhs_is_const != rhs_is_const:
                    # One side is a pure constant, other is a variable expression.
                    # Variables are stored at effect_scale; the goal expression uses
                    # scale_factor (= goal_scale).  Fetch the variable already rescaled
                    # to scale_factor, then apply the rational constant p/q via integer
                    # division — this gives c * actual * scale_factor correctly.
                    const_pred = predicate.lhs if lhs_is_const else predicate.rhs
                    var_pred   = predicate.rhs if lhs_is_const else predicate.lhs
                    c = Fraction(str(float(const_pred.value))).limit_denominator(10000)
                    var_expr = SMTExpression.fromPddl(var_pred, variables, bv=bv, width=width, scale_factor=scale_factor, effect_scale=effect_scale)
                    # _bv_const_mul requires a non-negative multiplier; handle sign separately
                    abs_numer = abs(c.numerator)
                    scaled = _bv_const_mul(var_expr.expression, abs_numer, width)
                    if c.denominator > 1:
                        scaled = BVUDiv(scaled, to_bv(c.denominator, width))
                    if c.numerator < 0:
                        from pysmt.shortcuts import BVSub
                        scaled = BVSub(to_bv(0, width), scaled)
                    result = SMTExpression()
                    result.variables = var_expr.variables
                    result.type = BVType(width)
                    result.expression = scaled
                    return result
            lhs = SMTExpression.fromPddl(predicate.lhs, variables, bv=bv, width=width, scale_factor=scale_factor, effect_scale=effect_scale)
            rhs = SMTExpression.fromPddl(predicate.rhs, variables, bv=bv, width=width, scale_factor=scale_factor, effect_scale=effect_scale)
            return SMTExpression.opByString(predicate.operator, lhs, rhs)
        if isinstance(predicate, Literal):
            bv_var = variables[predicate.getAtom()]
            if bv and effect_scale is not None and scale_factor > effect_scale:
                # State variables are stored at effect_scale; rescale to scale_factor.
                ratio = scale_factor // effect_scale
                result = SMTExpression()
                result.variables = bv_var.variables
                result.type = BVType(width)
                result.expression = _bv_const_mul(bv_var.expression, ratio, width)
                return result
            return bv_var
        if isinstance(predicate, Constant):
            if not bv:
                return predicate.value
            int_val = round(float(predicate.value) * scale_factor)
            expr = SMTExpression()
            expr.expression = to_bv(int_val, width)
            expr.type = BVType(width)
            expr.variables = set()
            return expr
    @classmethod
    def andOfExpressionsList(cls, rules: [SMTExpression]):
        if not rules: return TRUE()
        final: SMTExpression = rules[0]
        for rule in rules[1:]:
            final = final.AND(rule)
        return final

    @classmethod
    def orOfExpressionsList(cls, rules: [SMTExpression]):
        if not rules: return TRUE()
        final: SMTExpression = rules[0]
        for rule in rules[1:]:
            final = final.OR(rule)
        return final