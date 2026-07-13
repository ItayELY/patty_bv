"""List every PDDL domain file whose influence graph has a cycle.

Usage:
    python -m causal_cycles.list_cyclic_domains
    python -m causal_cycles.list_cyclic_domains files/ipc2026-dataset-main
    python -m causal_cycles.list_cyclic_domains -o cyclic_domains.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from causal_cycles.cli import _collect_domain_files
from causal_cycles.influence_graph import build_influence_graph_from_file


def find_cyclic_domains(paths: List[str]) -> List[Path]:
    cyclic = []
    for path in _collect_domain_files(paths, recursive=True):
        graph = build_influence_graph_from_file(str(path))
        if graph.cycles():
            cyclic.append(path)
    return cyclic


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", nargs="*", default=["files"],
        help="domain file(s)/directories to scan, recursively (default: files)",
    )
    parser.add_argument("-o", "--output", help="write the list to this file instead of stdout")
    args = parser.parse_args(argv)

    cyclic = find_cyclic_domains(args.paths)
    text = "".join(f"{p}\n" for p in cyclic)

    if args.output:
        Path(args.output).write_text(text)
        print(f"{len(cyclic)} domain(s) with cycles written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
        print(f"{len(cyclic)} domain(s) with cycles", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
