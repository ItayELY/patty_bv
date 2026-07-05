import time
import sys
from bitwuzla import Parser, TermManager, Options

dump_file = sys.argv[1] if len(sys.argv) > 1 else "smtlib_dump"

tm = TermManager()
opts = Options()
p = Parser(tm, opts, 'smt2')

t_parse_start = time.perf_counter()
p.parse(dump_file, False, True)
t_parse_end = time.perf_counter()

t_solve_start = time.perf_counter()
result = p.bitwuzla().check_sat()
t_solve_end = time.perf_counter()

print(f"Result:     {result}")
print(f"Parse time: {t_parse_end - t_parse_start:.3f}s")
print(f"Solve time: {t_solve_end - t_solve_start:.3f}s")
print(f"Total time: {t_solve_end - t_parse_start:.3f}s")
