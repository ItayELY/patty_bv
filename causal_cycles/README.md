# causal_cycles

Reads a PDDL domain and builds a directed **influence graph** over its
numeric variables (functions/fluents): an edge `y -> x` means some action,
process, or event's effect assigns a new value to `x` using an expression
that reads `y`. Self-loops (`x := 2 * x`) and multi-node cycles
(`x := y + 1`, `y := x + 1`) are both detected.

Variables are identified by function *name* only (schema/lifted level, e.g.
`(x ?obj)` and `(x ?other)` are both just `x`) — no grounded problem file is
required.

Effects recognized: `assign`, `increase`, `decrease`, `scale-up`,
`scale-down`, including ones nested in `and`, `forall`, `when`, and
durative-action `(at start ...)`/`(at end ...)` wrappers.

## Usage

```bash
# single domain, list every influence edge
python3 -m causal_cycles.cli files/tpp/domain.pddl -v

# scan a whole benchmark tree, write one .dot file per domain
python3 -m causal_cycles.cli files -r --dot-dir /tmp/dots

# use in CI-style checks: exit 1 if any scanned domain has a cycle
python3 -m causal_cycles.cli files -r --fail-on-cycle
```

Render a `.dot` file with Graphviz (nodes/edges on a cycle are colored red):

```bash
dot -Tpng /tmp/dots/tpp.dot -o tpp.png
```

## Files

- `sexpr.py` — minimal dependency-free S-expression reader for PDDL.
- `influence_graph.py` — walks a parsed domain's effects into a `DiGraph`.
- `graph.py` — small directed graph with Tarjan SCC-based cycle detection
  and Graphviz DOT export (no networkx dependency).
- `cli.py` — command-line entry point.
