from __future__ import annotations
import re
from typing import Dict, List, Set

from src.pddl.Atom import Atom
from src.pddl.Literal import Literal
from src.pddl.Operation import Operation
from src.pddl.Problem import Problem
from src.pddl.Utilities import Utilities
from src.pddl.Action import Action
from src.pddl.Event import Event
from src.pddl.Process import Process
from src.pddl.Type import Type
from src.pddl.TypedPredicate import TypedPredicate

from src.pddl.grammar.pddlParser import pddlParser


class Domain:
    name = str
    requirements: List[str]
    types: Dict[str, Type]
    predicates: set[TypedPredicate]
    functions: set[TypedPredicate]
    actions: set[Action]
    events: set[Event]
    processes: set[Process]
    __operationsDict: Dict[str, Operation]

    def __init__(self):
        self.types = dict()
        self.predicates = set()
        self.functions = set()
        self.actions = set()
        self.processes = set()
        self.events = set()
        self.requirements = list()
        self.constants: Dict[str, List[str]] = dict()
        pass

    def ground(self, problem: Problem, avoidSimplification=False) -> GroundedDomain:

        for typeName, objects in self.constants.items():
            problem.objectsByType.setdefault(typeName, [])
            for obj in objects:
                if obj not in problem.objectsByType[typeName]:
                    problem.objectsByType[typeName].append(obj)

        # Build static-predicate filter: skip combinations where a never-modified
        # positive precondition is false in the initial state (handles domains like
        # 2048 where pos-at/next facts constrain the huge constant parameter space).
        dynamicPredicateNames: Set[str] = set()
        for op in self.actions | self.events | self.processes:
            for atom in op.getAddList() | op.getDelList():
                dynamicPredicateNames.add(atom.name)

        initPredicates: Set[Atom] = set()
        for assignment in problem.init:
            if isinstance(assignment, Literal) and assignment.sign == "+":
                initPredicates.add(assignment.getAtom())

        gActions: Set[Action] = set([g for action in self.actions for g in action.ground(problem, initPredicates, dynamicPredicateNames)])
        gEvents: Set[Event] = set([g for event in self.events for g in event.ground(problem, initPredicates, dynamicPredicateNames)])
        gProcess: Set[Process] = set([g for process in self.processes for g in process.ground(problem, initPredicates, dynamicPredicateNames)])

        gDomain = GroundedDomain(self.name, gActions, gEvents, gProcess)

        if avoidSimplification:
            return gDomain

        from src.pddl.RPG import RPG
        from src.pddl.ARPG import ARPG

        constants: Dict[Atom, float] = dict()

        for op in gActions | gEvents | gProcess:
            for fun in op.getFunctions():
                if fun not in problem.init.numericAssignments:
                    # print(f"WARNING: {fun} was not initialized. Substituting it with 0")
                    constants[fun] = 0

        gDomain = gDomain.substitute(constants)

        rpg = RPG(gDomain, problem)
        orderedActions = rpg.getActionsOrder()
        arpg = ARPG(orderedActions, problem, gDomain)

        gDomain.actions = orderedActions
        constants: Dict[Atom, float] = arpg.getConstantAtoms()

        for op in gActions | gEvents | gProcess:
            for fun in op.getFunctions():
                if fun not in problem.init.numericAssignments:
                    # print(f"WARNING: {fun} was not initialized. Substituting it with 0")
                    constants[fun] = 0

        gDomain = gDomain.substitute(constants)
        orderedActions = [a.substitute(constants) for a in orderedActions if a.canHappen(constants)]
        problem.substitute(constants)

        gDomain.arpg = ARPG(orderedActions, problem, gDomain)
        return gDomain

    @classmethod
    def fromNode(cls, node: pddlParser.DomainContext) -> Domain:

        domain = cls()

        for i in range(node.getChildCount()):
            child = node.getChild(i)
            if isinstance(child, pddlParser.DomainNameContext):
                domain.__setDomainName(child)
            elif isinstance(child, pddlParser.RequirementsContext):
                domain.__setRequirementsList(child)
            elif isinstance(child, pddlParser.TypesContext):
                domain.__setTypesList(child)
            elif isinstance(child, pddlParser.PredicatesContext):
                domain.__setPredicates(child)
            elif isinstance(child, pddlParser.FunctionsContext):
                domain.__setFunctions(child)
            elif isinstance(child, pddlParser.ActionContext):
                domain.actions.add(Action.fromNode(child, domain.types))
            elif isinstance(child, pddlParser.EventContext):
                domain.events.add(Event.fromNode(child, domain.types))
            elif isinstance(child, pddlParser.ProcessContext):
                domain.processes.add(Process.fromNode(child, domain.types))

        return domain

    @staticmethod
    def _extractConstantsBlock(domainString: str):
        """Remove (:constants ...) from domain string and return (inner_text, remaining)."""
        match = re.search(r'\(\s*:constants', domainString)
        if not match:
            return None, domainString
        start = match.start()
        depth = 0
        for i in range(start, len(domainString)):
            if domainString[i] == '(':
                depth += 1
            elif domainString[i] == ')':
                depth -= 1
                if depth == 0:
                    inner = domainString[match.end():i].strip()
                    remaining = domainString[:start] + domainString[i + 1:]
                    return inner, remaining
        return None, domainString

    @staticmethod
    def _parseTypedList(text: str) -> Dict[str, List[str]]:
        """Parse 'obj1 obj2 - type ...' text into Dict[type, List[obj]]."""
        fake = f"(define (problem p) (:domain d) (:objects {text}))"
        parseTree = Utilities.getParseTree(fake)
        result: Dict[str, List[str]] = {}
        for node in parseTree.problem().getChildren():
            if not isinstance(node, pddlParser.ObjectsContext):
                continue
            for typeNode in node.children:
                if not isinstance(typeNode, pddlParser.TypedObjectsContext):
                    continue
                typeStr = ""
                objects = []
                for child in typeNode.children:
                    if isinstance(child, pddlParser.GroundAtomParameterContext):
                        objects.append(child.getText())
                    elif isinstance(child, pddlParser.TypeNameContext):
                        typeStr = child.getText()
                result.setdefault(typeStr, [])
                result[typeStr].extend(objects)
        return result

    @classmethod
    def fromFile(cls, filename) -> Domain:
        f = open(filename, 'r')
        domainString = f.read()
        f.close()
        domainString = Utilities.removeComments(domainString)

        constants_text, domainString = cls._extractConstantsBlock(domainString)

        # :action-costs is lexed as :action (keyword) + - + costs, which breaks the parser
        domainString = re.sub(r':action-costs\b', ':fluents', domainString)

        parseTree: pddlParser = Utilities.getParseTree(domainString)
        domain = cls.fromNode(parseTree.domain())

        if constants_text:
            domain.constants = cls._parseTypedList(constants_text)

        return domain

    def __setDomainName(self, node: pddlParser.DomainNameContext):
        self.name = node.getChild(2).getText()

    def __setRequirementsList(self, node: pddlParser.RequirementsContext):
        for child in node.children:
            if not isinstance(child, pddlParser.RequireKeyContext):
                continue
            self.requirements.append(child.getText())

    def __setTypesList(self, node: pddlParser.TypesContext):
        for typeRows in node.children:
            if not isinstance(typeRows, pddlParser.TypeContext):
                continue

            parent = None
            if typeRows.parent:
                name = typeRows.parent.getChild(1).getText()
                self.types[name] = self.types.setdefault(name, Type(name))
                parent = self.types[name]

            for t in typeRows.children:
                if not isinstance(t, pddlParser.TypeNameContext):
                    continue
                name = t.getText()
                self.types[name] = self.types.setdefault(name, Type(name, parent))
                if parent:
                    parent.addChild(self.types[name])

        pass

    def __setPredicates(self, node: pddlParser.PredicatesContext):
        for child in node.children:
            if not isinstance(child, pddlParser.PositiveLiteralContext):
                continue
            self.predicates.add(TypedPredicate.fromNode(child, self.types))

    def __setFunctions(self, node: pddlParser.FunctionsContext):
        for child in node.children:
            if not isinstance(child, pddlParser.PositiveLiteralContext):
                continue
            self.functions.add(TypedPredicate.fromNode(child, self.types))


class GroundedDomain(Domain):
    __operationsDict: Dict[str, Operation] = dict()
    functions: Set[Atom]
    predicates: Set[Atom]
    pre: Dict[Atom, Set[Operation]]
    preN: Dict[Atom, Set[Operation]]
    preB: Dict[Atom, Set[Operation]]
    addList: Dict[Atom, Set[Operation]]
    delList: Dict[Atom, Set[Operation]]
    assList: Dict[Atom, Set[Operation]]

    def __init__(self, name: str, actions: Set[Action], events: Set[Event], process: Set[Process]):
        super().__init__()

        self.name = name
        self.actions = actions
        self.events = events
        self.processes = process

        self.substitutions = dict()

        self.operations: Set[Operation] = set()
        self.operations.update(self.actions)
        self.operations.update(self.events)
        self.operations.update(self.processes)

        self.functions: Set[Atom] = set()
        self.predicates: Set[Atom] = set()
        self.allAtoms: Set[Atom] = set()
        self.preB: Dict[Atom, Set[Operation]] = dict()
        self.addList: Dict[Atom, Set[Operation]] = dict()
        self.delList: Dict[Atom, Set[Operation]] = dict()
        self.assList: Dict[Atom, Set[Operation]] = dict()

        for op in self.operations:
            self.__operationsDict[op.planName] = op
            self.functions |= op.getFunctions()
            self.predicates |= op.getPredicates()

            for v in op.getPreB():
                self.preB.setdefault(v, set())
                self.preB[v].add(op)
            for v in op.getAddList():
                self.addList.setdefault(v, set())
                self.addList[v].add(op)
            for v in op.getDelList():
                self.delList.setdefault(v, set())
                self.delList[v].add(op)
            for v in op.getAssList():
                self.assList.setdefault(v, set())
                self.assList[v].add(op)

        self.allAtoms = self.functions | self.predicates
        self.arpg = None

    def getOperationByPlanName(self, planName) -> Operation:
        return self.__operationsDict[planName]

    def substitute(self, sub: Dict[Atom, float], default=None) -> GroundedDomain:
        subActions: Set[Action] = {a.substitute(sub, default) for a in self.actions if a.canHappen(sub, default)}

        return GroundedDomain(self.name, subActions, self.events, self.processes)


    def getARPG(self):
        return self.arpg
