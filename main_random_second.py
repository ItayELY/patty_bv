import random
import traceback
from typing import List

from src.pddl.Domain import Domain, GroundedDomain
from src.pddl.NumericPlan import NumericPlan
from src.pddl.Operation import Operation
from src.pddl.Problem import Problem
from src.plan.PDDL2SMT import PDDL2SMT
from src.plan.Pattern import Pattern
from src.smt.SMTSolver import SMTSolver
from src.utils.Arguments import Arguments
from src.utils.LogPrint import LogPrint, LogPrintLevel
from src.utils.TimeStat import TimeStat

# -o patty\files\tpp\domain.pddl -f patty\files\tpp\instances\p05.pddl
def main():
    args = Arguments()
    if args.isHelp:
        exit(0)

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
        order = gDomain.getARPG().getActionsOrder()
        # elif args.pattern == "random":
        
        # else:
            # raise Exception(f"Pattern generation method '{args.pattern}' unknown")
        # pattern: Pattern = Pattern.fromOrder(order)
        pattern = Pattern.fromOrder(order)

        if args.printPattern:
            console.log("Pattern: " + str(pattern), LogPrintLevel.PLAN)

        # if args.printARPG:
        #     console.log(str(gDomain.arpg), LogPrintLevel.PLAN)
        while bound <= bMax:
            if bound > 1:
                
                order = list(gDomain.actions)
                random.shuffle(order)
            ts.start(f"Conversion to SMT at bound {bound}", console=console)
            pddl2smt: PDDL2SMT = PDDL2SMT(
                domain=gDomain,
                problem=problem,
                pattern=pattern,
                bound=bound,
                encoding=args.encoding,
                binaryActions=args.binaryActions,
                rollBound=args.rollBound,
                hasEffectAxioms=args.hasEffectAxioms
            )
            ts.end(f"Conversion to SMT at bound {bound}", console=console)

            ts.start(f"Solving Bound {bound}", console=console)
            solver: SMTSolver = SMTSolver(pddl2smt, solver=args.solver)
            # pddl2smt.printRules
            plan: NumericPlan
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
                    print(f"-------Step {idx}-------")
                    console.log(p.toValString(), LogPrintLevel.PLAN)
                    # isValid = p.validate(problem, avoidRaising=True, logger=console)
                    # if isValid:
                        # console.log("Plan is valid", LogPrintLevel.PLAN)
                        # if args.savePlan:
                            # fn = args.savePlan if args.savePlan != "PROBLEM" else args.problem + ".plan"
                            # with open(fn, "w") as f:
                                # f.write(p.toValString())
                    # else:
                        # console.log("Plan is NOT valid", LogPrintLevel.PLAN)
                console.log(f"Bound: {bound}", LogPrintLevel.STATS)

                break

            bound += 1

        ts.end("Overall")
        console.log(str(ts), LogPrintLevel.TIMES)

    except:
        print("Something went wrong.")
        traceback.print_exc()


if __name__ == '__main__':
    main()


'''
Pattern: drive truck0 depot0 market4; drive truck0 depot0 market5; drive truck0 depot0 market1; drive truck0 depot0 market3; drive truck0 depot0 market2; drive truck0 market5 depot0; buy-all truck0 goods4 market5; drive truck0 market4 market2; drive truck0 market4 market1; drive truck0 market4 market3; drive truck0 market1 market3; drive truck0 market2 market5; drive truck0 market4 depot0; drive truck0 market2 depot0; buy-allneeded truck0 goods2 market2; buy-all truck0 goods3 market1; drive truck0 market3 market2; drive truck0 market1 depot0; drive truck0 market3 market1; buy-all truck0 goods0 market1; buy-all truck0 goods1 market4; drive truck0 market2 market4; buy-all truck0 goods0 market2; drive truck0 market3 depot0; drive truck0 market1 market4; buy-all truck0 goods0 market3; buy-all truck0 goods4 market1; buy-all truck0 goods3 market2; drive truck0 market5 market4; buy-all truck0 goods4 market2; buy-all truck0 goods0 market4; drive truck0 market3 market5; drive truck0 market2 market1; drive truck0 market4 market5; buy-all truck0 goods1 market3; drive truck0 market1 market2; drive truck0 market5 market2; drive truck0 market5 market1; buy-allneeded truck0 goods2 market5; drive truck0 market1 market5; ###drive truck0 market3 market4### ; buy-all truck0 goods4 market3; buy-all truck0 goods0 market5; ### drive truck0 market2 market3 ###; drive truck0 market5 market3; buy-allneeded truck0 goods0 market1; buy-allneeded truck0 goods3 market1; buy-all truck0 goods2 market2; buy-allneeded truck0 goods4 market5; buy-allneeded truck0 goods1 market3; buy-allneeded truck0 goods0 market5; buy-allneeded truck0 goods0 market2; *** buy-allneeded truck0 goods0 market4 ***; buy-allneeded truck0 goods4 market2; buy-allneeded truck0 goods3 market2; buy-allneeded truck0 goods4 market1; *** buy-allneeded truck0 goods4 market3 *** ; buy-all truck0 goods2 market5; buy-allneeded truck0 goods1 market4; buy-allneeded truck0 goods0 market3; drive truck0 depot0 depot0; drive truck0 market4 market4; drive truck0 market1 market1; drive truck0 market5 market5; drive truck0 market2 market2; drive truck0 market3 market3
'''