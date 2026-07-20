# check_almost_acyclic

Checks whether a PDDL domain's numeric task Πlt is **almost acyclic with
integer self-loops**:

1. The dependency variable-dependency graph G (over numeric
   variables/functions, edge `y -> x` iff some effect assigns `x` using an
   expression that reads `y`) is acyclic, **ignoring self-loops** (`x -> x`
   doesn't count as a cycle here - that's what condition 2 is for).
2. For each numeric variable `y` and each linear effect that assigns it,
   rewritten as `y := z*y + sum_{v != y} c_v * v`, the self-coefficient `z`
   is an integer.

A domain fails condition 1 if two or more distinct variables depend on each
other cyclically (e.g. `x := y + 1`, `y := x + 1`). It fails condition 2 if
some effect's self-coefficient is a non-integer constant (e.g. `cash :=
1.1 * cash`) or isn't even a constant - i.e. it depends on some *other*
variable (e.g. `v := r*v + ...`), which means the effect isn't of the
required linear form at all.

Variables are identified by function *name* only (schema/lifted level, same
as [`causal_cycles`](../causal_cycles/README.md), which this tool reuses for
condition 1 and for PDDL parsing) - no grounded problem file is required.

## Usage

```bash
python3 -m check_almost_acyclic.cli files/tpp/domain.pddl
```

```
=== files/tpp/domain.pddl ===
  [1] dependency graph acyclic (ignoring self-loops): FAIL - 1 cycle(s) found
        cycle: on-sale -> bought -> on-sale
  [2] integer self-loop coefficients: OK
  almost acyclic with integer self-loops: NO
```

A domain with a non-integer self-loop:

```
=== interest.pddl ===
  [1] dependency graph acyclic (ignoring self-loops): OK
  [2] integer self-loop coefficients: FAIL - 1 violation(s) found
        action 'accrue', effect (increase (cash) (* 0.1 (cash))): self-coefficient of 'cash' is z = 11/10, not an integer
  almost acyclic with integer self-loops: NO
```

Other options:

```bash
# scan a whole benchmark tree, exit 1 if any domain is not almost acyclic (CI-style)
python3 -m check_almost_acyclic.cli files -r --fail-on-violation
```

## Programmatic use

```python
from check_almost_acyclic.checker import check_domain_file

result = check_domain_file("files/tpp/domain.pddl")
result.is_almost_acyclic   # bool
result.condition1_ok       # bool
result.condition2_ok       # bool
result.cycles              # List[List[str]] - offending cycles in G, if any
result.self_loop_violations  # List[SelfLoopViolation] - the proof for condition 2
```

Each `SelfLoopViolation` carries the offending `NumericEffect` (action name,
operator, target variable, right-hand side) plus the computed coefficient
(or the non-constant witness expression when the effect isn't linear in its
target at all), so callers can print or otherwise use the counterexample
directly instead of re-deriving it.

## Files

- `linear_form.py` - walks a domain's numeric effects (same traversal as
  `causal_cycles.influence_graph`) and, for each one, uses `sympy` to
  rewrite it as `y := z*y + ...` and extract `z` exactly (as a `Rational`,
  never a float, so integrality checks are exact).
- `checker.py` - combines condition 1 (via `causal_cycles`'s graph) and
  condition 2 (via `linear_form`) into a single `AlmostAcyclicResult`.
- `cli.py` - command-line entry point.
