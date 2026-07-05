import time
import sys
import cvc5

dump_file = sys.argv[1] if len(sys.argv) > 1 else "smtlib_dump_regular"

tm = cvc5.TermManager()
solver = cvc5.Solver(tm)
solver.setOption("produce-models", "true")

sm = cvc5.SymbolManager(tm)
parser = cvc5.InputParser(solver, sm)

t_parse_start = time.perf_counter()
parser.setFileInput(cvc5.InputLanguage.SMT_LIB_2_6, dump_file)

result = None
t_solve_start = None
t_solve_end = None
while True:
    cmd = parser.nextCommand()
    if cmd.isNull():
        break
    if cmd.getCommandName() == "check-sat":
        t_solve_start = time.perf_counter()
    output = cmd.invoke(solver, sm)
    if cmd.getCommandName() == "check-sat":
        t_solve_end = time.perf_counter()
        result = output.strip()

t_total_end = time.perf_counter()

print(f"Result:     {result}")
print(f"Parse time: {t_solve_start - t_parse_start:.3f}s")
print(f"Solve time: {t_solve_end - t_solve_start:.3f}s")
print(f"Total time: {t_total_end - t_parse_start:.3f}s")
