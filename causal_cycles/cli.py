"""CLI: build the numeric-variable influence graph for one or more PDDL domains.

Usage:
    python -m causal_cycles.cli files/gardening/domain.pddl
    python -m causal_cycles.cli files/ --recursive --dot-dir /tmp/dots
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from causal_cycles.graph import DiGraph
from causal_cycles.influence_graph import build_influence_graph_from_file


def _looks_like_domain_file(path: Path) -> bool:
    if path.suffix.lower() != ".pddl":
        return False
    try:
        head = path.read_text(errors="ignore")[:2000]
    except OSError:
        return False
    return "(define" in head and "(domain" in head


def _collect_domain_files(paths: List[str], recursive: bool) -> List[Path]:
    files: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            pattern = "**/*.pddl" if recursive else "*.pddl"
            files.extend(sorted(f for f in p.glob(pattern) if _looks_like_domain_file(f)))
        else:
            print(f"warning: path not found: {raw}", file=sys.stderr)
    return files


def _report_for(path: Path, graph: DiGraph, verbose: bool) -> bool:
    """Prints a report for one domain file. Returns True iff a cycle exists."""
    print(f"\n=== {path} ===")
    if not graph.nodes:
        print("  no numeric variables / effects found")
        return False

    print(f"  variables ({len(graph.nodes)}): {', '.join(sorted(graph.nodes))}")

    if verbose:
        print("  edges:")
        for (s, t), labels in sorted(graph.edges.items()):
            via = f"  [{', '.join(sorted(labels))}]" if labels else ""
            print(f"    {s} -> {t}{via}")

    cycles = graph.cycles()
    if not cycles:
        print("  no cycles")
        return False

    print(f"  {len(cycles)} cycle(s) found:")
    for c in sorted(cycles, key=lambda c: (-len(c), c)):
        print(f"    {' -> '.join(c)}{' -> ' + c[0] if len(c) > 1 else ''}")
    return True


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="domain.pddl file(s) or directories to scan")
    parser.add_argument("-r", "--recursive", action="store_true", help="recurse into directories")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every influence edge")
    parser.add_argument("--dot-dir", help="write a Graphviz .dot file per domain into this directory")
    parser.add_argument("--fail-on-cycle", action="store_true", help="exit 1 if any domain has a cycle")
    args = parser.parse_args(argv)

    domain_files = _collect_domain_files(args.paths, args.recursive)
    if not domain_files:
        print("no domain PDDL files found", file=sys.stderr)
        return 2

    if args.dot_dir:
        Path(args.dot_dir).mkdir(parents=True, exist_ok=True)

    any_cycle = False
    for path in domain_files:
        graph = build_influence_graph_from_file(str(path))
        has_cycle = _report_for(path, graph, args.verbose)
        any_cycle = any_cycle or has_cycle

        if args.dot_dir:
            dot_path = Path(args.dot_dir) / f"{path.stem}.dot"
            dot_path.write_text(graph.to_dot(name=path.stem.replace("-", "_")))

    if args.fail_on_cycle and any_cycle:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
