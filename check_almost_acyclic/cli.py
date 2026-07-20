"""CLI: check whether one or more PDDL domains are "almost acyclic with
integer self-loops" (see check_almost_acyclic/README.md for the definition).

Usage:
    python -m check_almost_acyclic.cli files/tpp/domain.pddl
    python -m check_almost_acyclic.cli files/ --recursive --fail-on-violation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from causal_cycles.cli import _collect_domain_files

from check_almost_acyclic.checker import AlmostAcyclicResult, check_domain_file


def _report_for(path: Path, result: AlmostAcyclicResult) -> bool:
    """Prints a text report (with proof) for one domain. Returns True iff it is almost acyclic."""
    print(f"\n=== {path} ===")

    if result.condition1_ok:
        print("  [1] dependency graph acyclic (ignoring self-loops): OK")
    else:
        print(f"  [1] dependency graph acyclic (ignoring self-loops): FAIL - "
              f"{len(result.cycles)} cycle(s) found")
        for c in result.cycles:
            print(f"        cycle: {' -> '.join(c)} -> {c[0]}")

    if result.condition2_ok:
        print("  [2] integer self-loop coefficients: OK")
    else:
        print(f"  [2] integer self-loop coefficients: FAIL - "
              f"{len(result.self_loop_violations)} violation(s) found")
        for v in result.self_loop_violations:
            print(f"        {v}")

    verdict = "YES" if result.is_almost_acyclic else "NO"
    print(f"  almost acyclic with integer self-loops: {verdict}")
    return result.is_almost_acyclic


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="domain.pddl file(s) or directories to scan")
    parser.add_argument("-r", "--recursive", action="store_true", help="recurse into directories")
    parser.add_argument("--fail-on-violation", action="store_true",
                         help="exit 1 if any domain is not almost acyclic")
    args = parser.parse_args(argv)

    domain_files = _collect_domain_files(args.paths, args.recursive)
    if not domain_files:
        print("no domain PDDL files found", file=sys.stderr)
        return 2

    any_violation = False
    for path in domain_files:
        result = check_domain_file(str(path))
        ok = _report_for(path, result)
        any_violation = any_violation or not ok

    if args.fail_on_violation and any_violation:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
