from typing import Dict
from src.pddl.Action import Action
from src.pddl.Atom import Atom
from src.plan.TransitionVariables import TransitionVariables
from src.smt.SMTBVVariable import SMTBVVariable
from src.smt.SMTBoolVariable import SMTBoolVariable


class TransitionVariablesBV(TransitionVariables):
    def __init__(self, predicates, functions, assList, pattern, index, hasPlaceholders, width=10, action_width=None):
        self.width = width
        self.action_width = action_width if action_width is not None else width
        # We do NOT call super().__init__ because it would trigger the mangled parent methods
        
        self.functions = functions
        self.predicates = predicates
        self.assList = assList
        self.pattern = pattern
        
        # Now we call the local BV methods defined below
        self.valueVariables = self.__computeValueVariables(index)
        self.deltaVariables = self.__computeDeltaVariables(index, hasPlaceholders)
        
        if index > 0:
            self.actionVariables = self.__computeActionVariables(index)
            self.auxVariables = self.__computeAuxVariables(index)

    def __computeValueVariables(self, index: int):
        variables = dict()
        for atom in self.functions:
        # Pass self.width here
            variables[atom] = SMTBVVariable(f"{atom}_{index}", self.width)
        for atom in self.predicates:
            variables[atom] = SMTBoolVariable(f"{atom}_{index}")
        return variables

    # IMPORTANT: You must also override Delta variables, 
    # otherwise they will still be Reals from the parent class!
    def __computeDeltaVariables(self, index: int, hasPlaceholders: bool) -> Dict[Action, Dict[Atom, SMTBVVariable]]:
        variables = dict()
        for action in self.pattern:
            variables[action] = dict()
            if hasPlaceholders:
                for atom in self.functions:
                    variables[action][atom] = SMTBVVariable(f"d_{{{action}}}_{index}({atom})", self.width)
                for atom in self.predicates:
                    variables[action][atom] = SMTBoolVariable(f"d_{{{action}}}_{index}({atom})")
        return variables

    def __computeActionVariables(self, index: int):
        variables = dict()
        for action in self.pattern:
            if not action.isFake:
                variables[action] = SMTBVVariable(f"{action.name}_{index}_n", self.action_width)
        return variables

    def __computeAuxVariables(self, index) -> Dict[Action, Dict[Atom, SMTBVVariable]]:
        variables = dict()
        for (var, actions) in self.assList.items():
            for a in actions:
                variables.setdefault(a, dict())
                variables[a][var] = SMTBVVariable(f"{var}_{a}_{index}", self.width)
        
        for a in self.pattern:
            if a.hasNonSimpleLinearIncrement():
                for eff in a.effects:
                    if eff.isLinearIncrement():
                        var = eff.getAtom()
                        variables.setdefault(a, dict())
                        variables[a][var] = SMTBVVariable(f"{var}_{a}_{index}", self.width)
        return variables