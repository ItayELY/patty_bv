import random
import traceback
from typing import List

from src.pddl.Domain import Domain, GroundedDomain
from src.pddl.NumericPlan import NumericPlan
from src.pddl.Operation import Operation
from src.pddl.Problem import Problem
from src.plan.PDDL2SMTBV import PDDL2SMTBV

from src.plan.PatternBV import Pattern
from src.utils.Arguments import Arguments
from src.utils.LogPrint import LogPrint, LogPrintLevel
from src.utils.TimeStat import TimeStat

# -o patty\files\tpp\domain.pddl -f patty\files\tpp\instances\p05.pddl
def validate(node):

    from pysmt.fnode import FNode

    if not isinstance(node, FNode):
        print("BAD NODE:", node, type(node))
        return

    for c in node.args():
        validate(c)
def main():
    args = Arguments()
    if args.isHelp:
        exit(0)

    if args.solver == "bitwuzla":
        from src.smt.SMTSolverBV_Bitwuzla import SMTSolver
    else:
        from src.smt.SMTSolverBV_S import SMTSolver

    try:

        console: LogPrint = LogPrint(args.verboseLevel)
        ts: TimeStat = TimeStat()
        ts.start("Overall")
        domain: Domain = Domain.fromFile(args.domain)
        problem: Problem = Problem.fromFile(args.problem)

        ts.start("Grounding", console=console)
        gDomain: GroundedDomain = domain.ground(problem)
        ts.end("Grounding", console=console)

        bound = args.bound if args.bound else 1
        bMax = args.bound if args.bound else 1000

        order: List[Operation]
        # if args.pattern == "arpg":
        order = list(gDomain.actions)
        random.shuffle(order)        # elif args.pattern == "random":
        
        # else:
            # raise Exception(f"Pattern generation method '{args.pattern}' unknown")
        # pattern: Pattern = Pattern.fromOrder(order)
        pattern = Pattern.fromOrder(order)

        if args.printPattern:
            console.log("Pattern: " + str(pattern), LogPrintLevel.PLAN)

        # if args.printARPG:
        #     console.log(str(gDomain.arpg), LogPrintLevel.PLAN)
        while bound <= bMax:
            # if bound > 1:
                
                
            ts.start(f"Conversion to SMT at bound {bound}", console=console) 
            pddl2smt: PDDL2SMTBV = PDDL2SMTBV(
                domain=gDomain,
                problem=problem,
                pattern=pattern,
                bound=bound,
                encoding=args.encoding,
                binaryActions=args.binaryActions,
                rollBound=args.rollBound,
                hasEffectAxioms=args.hasEffectAxioms
            )
            # print("******* Rules")

            # print("******* Rules")
            ts.end(f"Conversion to SMT at bound {bound}", console=console)

            ts.start(f"Solving Bound {bound}", console=console)
            solver: SMTSolver = SMTSolver(pddl2smt, solver=args.solver)
            # pddl2smt.printRules
            plan: NumericPlan
            if args.saveSMT:
                filename = f"{args.saveSMT}-{bound}.smt"
                console.log(f"Saving to {filename}", LogPrintLevel.STATS)
                with open(f"{args.saveSMT}-{bound}.smt", "w") as f:
                    f.write(str(pddl2smt))
            if args.deep:
                plan = solver.optimizeBinary()
            else:
                plan = solver.solve()
            solver.exit()
            ts.end(f"Solving Bound {bound}", console=console)

            console.log(f"Bound {bound} - Vars = {pddl2smt.getNVars()}", LogPrintLevel.STATS)
            console.log(f"Bound {bound} - Rules = {pddl2smt.getNRules()}", LogPrintLevel.STATS)

            if args.saveSMT:
                filename = f"{args.saveSMT}-{bound}.smt"
                console.log(f"Saving to {filename}", LogPrintLevel.STATS)
                with open(f"{args.saveSMT}-{bound}.smt", "w") as f:
                    f.write(str(pddl2smt))

            if not plan:
                console.log(
                    f"NO SOLUTION: A solution could not be found with bound {bound}. Try to increase the bound",
                    LogPrintLevel.PLAN)
            else:
                for idx, p in enumerate(plan):
                    console.log(f"-------Step {idx}-------", LogPrintLevel.STEPS)
                    console.log(p.toValString(), LogPrintLevel.PLAN)

                wholePlan = NumericPlan()
                for p in plan:
                    for action in p:
                        wholePlan.addRepeatedAction(action, 1)

                isValid = wholePlan.validate(problem, avoidRaising=True, logger=console)
                if isValid:
                    console.log("Plan is valid", LogPrintLevel.PLAN)
                    if args.savePlan:
                        fn = args.savePlan if args.savePlan != "PROBLEM" else args.problem + ".plan"
                        with open(fn, "w") as f:
                            f.write(wholePlan.toValString())
                else:
                    console.log("Plan is NOT valid", LogPrintLevel.PLAN)
                console.log(f"Bound: {bound}", LogPrintLevel.STATS)

                break

            bound += 1

        ts.end("Overall")
        console.log(str(ts), LogPrintLevel.TIMES)

    except Exception:
        traceback.print_exc()


if __name__ == '__main__':
    main()

# z3:
'''
Bound: 2
Grounding: 78ms
Conversion to SMT at bound 1: 127ms
Solving Bound 1: 1635ms
Conversion to SMT at bound 2: 226ms
Solving Bound 2: 10399ms
Overall: 12569ms'''


'''
-------Step 0-------
0: (drive truck0 depot0 market3)
1: (buy-all truck0 goods1 market3)
2: (buy-all truck0 goods0 market3)

-------Step 1-------
0: (drive truck0 market3 market4)
1: (drive truck0 market4 depot0)
'''

'''
0: (go_south_west b1)
1: (go_south_west b1)
2: (go_south_west b1)
3: (go_south_west b1)
4: (go_south_west b1)
5: (go_south_west b1)
6: (go_south b2)
7: (go_south b2)
8: (go_south b2)
9: (go_south b2)
10: (go_south b2)
11: (go_south b2)
12: (go_south b2)
13: (go_south b2)
14: (go_south b2)
15: (go_south b2)
16: (go_south b2)
17: (go_south b2)
18: (go_south b2)
19: (go_south b2)
20: (go_south b2)
21: (go_south b2)
22: (go_south b2)
23: (go_south b2)
24: (go_south b2)
25: (go_south b2)
26: (go_south b2)
27: (go_south b2)
28: (save_person b2 p1)
29: (save_person b0 p5)
30: (save_person b2 p2)
31: (save_person b0 p0)
32: (save_person b2 p4)
33: (save_person b1 p3)
'''