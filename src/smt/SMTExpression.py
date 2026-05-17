from __future__ import annotations
from typing import Set, Dict

from pysmt.fnode import FNode
from pysmt.shortcuts import (
    And, Or, Equals, LE, LT, GE, GT, Implies, Real, Times, Minus, Plus, Div,
    TRUE, ToReal, Int, NotEquals, Iff, BV, Not,
    BVAdd, BVSub, BVMul, BVULT, BVULE, BVUGT, BVUGE, BVUGT, Ite, BVSGE, BVSLE, BVSGT, BVSLT,
    BVUDiv
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
                 
        # 1. Ensure we are working with raw expressions
        lhs_raw = lhsExpression.expression if hasattr(lhsExpression, 'expression') else lhsExpression
        rhs_raw = rhsExpression.expression if hasattr(rhsExpression, 'expression') else rhsExpression

# 2. Use the environment's Static Type Checker (STC)
        from pysmt.environment import get_env
        stc = get_env().stc
        l_type = stc.get_type(lhs_raw)
        try:
            r_type = stc.get_type(rhs_raw)
        except:
            pass
        # 1. BIT-VECTOR PATH (Priority)
        vars_lhs = getVars(self)
        vars_rhs = getVars(other)
        combined_vars = vars_lhs | vars_rhs
        is_bv = (l_type and l_type.is_bv_type()) or (r_type and r_type.is_bv_type())
        
        if is_bv:
            if l_type != r_type:
                try:
                    target_width = rhsExpression.bv_width()
                    lhsExpression = to_bv(int(float(str(lhsExpression))), target_width)
                except:
                    target_width = lhsExpression.bv_width()
                    rhsExpression = to_bv(int(float(str(rhsExpression))), target_width)
            target_bv_type = l_type if (l_type and l_type.is_bv_type()) else r_type
            expr = SMTExpression()
            expr.variables = combined_vars
            expr.type = target_bv_type
                
            # Map Arithmetic/Comparison to BV Equivalents
            bv_map = {
                Plus: BVAdd, Minus: BVSub, Times: BVMul,
                LT: BVSLT, LE: BVSLE, GT: BVSGT, GE: BVSGE,
                Equals: Equals, NotEquals: lambda l, r: Not(Equals(l, r))
            }
            
            actual_op = bv_map.get(operation, operation)
            
            # PERFORMANCE OPTIMIZATION:
            # Multiplications in BV are slow. If we are multiplying a variable by a constant,
            # use an Ite (If-Then-Else) logic for binary action counts.
            # Inside your __binary method for the is_bv path:

            if actual_op == BVMul:
    # If multiplying by a constant 1, just return the variable
                if rhsExpression.is_constant() and rhsExpression.constant_value() == 1:
                    expr.expression = lhsExpression
    # If multiplying by a constant 0, return constant 0
                elif rhsExpression.is_constant() and rhsExpression.constant_value() == 0:
                    expr.expression = to_bv(0, target_bv_type.width)
                else:
                    rhs_bv = to_bv(rhsExpression.constant_value(), target_bv_type.width) if rhsExpression.is_constant() else rhsExpression
                    expr.expression = BVMul(lhsExpression, rhs_bv)
                
                return expr
            if actual_op == BVSub:
                width = target_bv_type.width
    
    # 1. Standard Case: Variable - Constant (e.g., fuel - 1)
                if rhsExpression.is_constant():
                    k = rhsExpression.constant_value()
        # If subtracting 0, just return the variable
                    if k == 0:
                        expr.expression = lhsExpression
                    else:
                        expr.expression = BVSub(lhsExpression, to_bv(k, width))

    # 2. Reverse Case: Constant - Variable (e.g., 20 - bought)
                elif lhsExpression.is_constant():
                    k = lhsExpression.constant_value()
        # Optimization: We cannot use a simple ITE here like in BVMul 
        # because the variable being subtracted isn't necessarily binary.
        # We just ensure the constant k is correctly cast to a Bit-Vector.
                    expr.expression = BVSub(to_bv(k, width), rhsExpression)
        
    # 3. Variable - Variable Case
                else:
                    expr.expression = BVSub(lhsExpression, rhsExpression)

                return expr

        # 2. INTEGER/REAL FALLBACK (Only runs if not BV)
        if l_type == REAL and r_type == INT:
            rhsExpression = ToReal(rhsExpression)
        elif l_type == INT and r_type == REAL:
            lhsExpression = ToReal(lhsExpression)
            
        expr = SMTExpression()
        expr.variables = getVars(self) | getVars(other)
        expr.type = l_type if l_type == r_type else REAL
        try:
            expr.expression = operation(lhsExpression, rhsExpression) if not is_bv else actual_op(lhsExpression, rhsExpression)
        except: 
            pass
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
                 variables: Dict[Atom, SMTExpression], bv=False, width = 0, scale_factor=1) -> SMTExpression or float:
        if isinstance(predicate, BinaryPredicate):
            lhs = SMTExpression.fromPddl(predicate.lhs, variables, bv=bv, width=width, scale_factor=scale_factor)
            rhs = SMTExpression.fromPddl(predicate.rhs, variables, bv=bv, width=width, scale_factor=scale_factor)
            result = SMTExpression.opByString(predicate.operator, lhs, rhs)
            # In BV mode, both operands are already scaled by scale_factor, so
            # their product is scale_factor^2 times the real value. Divide by
            # scale_factor to correct back to a single-scaled BV value.
            if bv and predicate.operator == "*" and scale_factor > 1:
                raw = result.expression if hasattr(result, 'expression') else result
                div_expr = SMTExpression()
                div_expr.variables = getattr(result, 'variables', set())
                div_expr.type = getattr(result, 'type', BVType(width))
                div_expr.expression = BVUDiv(raw, BV(scale_factor, width))
                return div_expr
            return result
        if isinstance(predicate, Literal):
            return variables[predicate.getAtom()]
        if isinstance(predicate, Constant):
            if not bv:
                return predicate.value
            int_val = round(float(predicate.value) * scale_factor)
            # wrapper:
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