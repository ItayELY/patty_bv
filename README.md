# PATTY / PattyInt — AAAI 2027 Supplemental Material

This archive contains the source code, benchmark data, and scripts needed
to reproduce the experiments reported in the paper. It contains two
planners built on the same symbolic pattern-planning core:

- **PATTY** (`main.py`) — the original SMT encoding, solved over linear
  real/nonlinear arithmetic (LRA/NRA).
- **PattyInt** (`main_bv.py`) — this paper's contribution: an integer
  bit-vector (QF_BV) compilation of the same encoding, solved with
  [Bitwuzla](https://bitwuzla.github.io/).

## Contents

- `src/` — the shared SMT-encoding core (PDDL parsing, pattern
  construction, and the SMT encoders for both the LRA/NRA and QF_BV
  backends).
- `main.py`, `main_bv.py` — command-line entry points for PATTY and
  PattyInt respectively.
- `benchmarks/` — the evaluation harness (`benchmark_local.py`), the
  instance lists used in the paper (`instances_all.csv`,
  `instances_enhsp.csv`), and the planner-wrapper classes
  (`benchmarks/classes/`) used to drive each solver and parse its output.
- `files_itay/` — the PDDL domains and instances used for the results
  reported in the paper.
- `causal_cycles/` and `check_almost_acyclic/` — standalone tools that
  implement the paper's theoretical "almost acyclic with integer
  self-loops" discretizability condition (Section on the Discretizable
  Fragment): `causal_cycles` builds the numeric-variable influence graph
  from a PDDL domain, and `check_almost_acyclic` checks the acyclicity +
  integer-self-loop condition on top of it.
- `tests/` — unit tests for the encoding.

**Not included** (external dependencies, not part of this paper's
contribution): the ENHSP, NFD, and Springroll baseline planners used as
comparison points in the evaluation. These are large, separately
distributed systems; install them from their own official sources if you
want to reproduce the ENHSP/NFD columns specifically. Everything needed
to reproduce the PATTY vs. PattyInt comparison is self-contained here.

## Installation

Two options, either is sufficient to run PATTY/PattyInt:

**Option A — conda:**
```bash
conda env create -f environment.yml
conda activate patty
pip install bitwuzla antlr4-python3-runtime==4.12.0
```

**Option B — plain virtualenv, via the provided script:**
```bash
./compile        # builds a local .venv/ with pysmt, sympy, bitwuzla, antlr4
```

Then generate the convenience wrapper scripts (`patty`, `pattyBV`):
```bash
./install
```

## Running a single instance

```bash
# PATTY (original LRA/NRA encoding)
./patty -o <domain.pddl> -f <problem.pddl> --solver z3 --pattern arpg

# PattyInt (this paper's integer bit-vector encoding)
./pattyBV -o <domain.pddl> -f <problem.pddl> --solver bitwuzla --pattern arpg
```

Both accept `--save-plan <file>` to write the found plan, and
`-v <level>` to control verbosity. See `src/utils/Arguments.py` for the
full flag list.

A quick end-to-end smoke test (mirrors the IPC submission format this
codebase was also built for) is available via:
```bash
./test-submission.sh --local
```

## Reproducing the paper's benchmark tables

`benchmarks/benchmark_local.py` runs a planner over a CSV list of
`(planner, domain_name, domain_file, problem_file)` rows and appends one
result line per instance to a per-worker log file. The instance lists
used for the paper's reported tables are `benchmarks/instances_all.csv`
(PATTY, PATTY-BV, and ENHSP over `files_itay/`) and
`benchmarks/instances_enhsp.csv` (the ENHSP-only subset, used to rerun
just that solver — see `merge_enhsp_log.py` for combining a separate
ENHSP run back into a combined results log).

```bash
cd benchmarks
EXPERIMENT_NAME=<output_dir> TIMEOUT=300 FILE=instances_all.csv \
    python benchmark_local.py --workers <N>
```

Each output row is `solver,domain,problem,solved,timeout,time_ms,bound,
planLength,nOfVars,nOfRules,lastSearchedBound` (see
`benchmarks/classes/Result.py`). The per-domain Coverage/Time/Agile-Score
tables in the paper are computed from this format.

## Checking the discretizable-fragment condition

```bash
python -m check_almost_acyclic.cli <domain.pddl>
python -m check_almost_acyclic.cli files_itay/ --recursive
```

Reports, per domain, whether its numeric-variable dependency graph is
acyclic (ignoring self-loops) and whether every self-loop coefficient is
an integer — the condition under which PattyInt's integer lifting is
guaranteed to be exact (see `check_almost_acyclic/README.md` and
`causal_cycles/README.md` for details).

## License

MIT License, see `LICENSE`.
