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

By default this just prints a text description of the graph — variables,
every edge (with the action name(s) that cause it), and any cycles:

```bash
python3 -m causal_cycles.cli files/tpp/domain.pddl
```

```
=== files/tpp/domain.pddl ===
  variables (6): bought, drive-cost, on-sale, price, request, total-cost
  edges:
    bought -> on-sale  via: buy-allneeded
    on-sale -> bought  via: buy-all
    ...
  1 cycle(s) found:
    on-sale -> bought -> on-sale
```

Other options:

```bash
# scan a whole benchmark tree, exit 1 if any domain has a cycle (CI-style)
python3 -m causal_cycles.cli files -r --fail-on-cycle

# write a self-contained, interactive .html per domain instead (draggable
# nodes, cyclic nodes/edges highlighted red, hover an edge for its action
# name) - only useful if you have a browser to open it with
python3 -m causal_cycles.cli files/tpp/domain.pddl --html-dir /tmp/graphs

# or write a Graphviz .dot file per domain (needs `apt-get install graphviz`
# to render): dot -Tpng /tmp/dots/tpp.dot -o tpp.png
python3 -m causal_cycles.cli files -r --dot-dir /tmp/dots
```

## Files

- `sexpr.py` — minimal dependency-free S-expression reader for PDDL.
- `influence_graph.py` — walks a parsed domain's effects into a `DiGraph`.
- `graph.py` — small directed graph with Tarjan SCC-based cycle detection,
  Graphviz DOT export, and per-edge/per-node cycle membership (no networkx
  dependency).
- `html_render.py` — renders a `DiGraph` as a self-contained interactive
  HTML page (inline vanilla-JS force-directed layout, no CDN/graphviz).
- `cli.py` — command-line entry point.
