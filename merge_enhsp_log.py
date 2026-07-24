"""
Merge ENHSP rows into combined_all.log.

Takes every row from combined_all.log as-is, drops any ENHSP rows already in
there (so this is safe to re-run), and appends the ENHSP rows pulled out of
combined_all_with_ENHSP.log. Writes the result back to combined_all.log.
"""

import shutil

COMBINED_ALL = "combined_all.log"
COMBINED_ALL_WITH_ENHSP = "combined_enhsp.log"


def solver_of(line: str) -> str:
    return line.split(",", 1)[0]


def main():
    with open(COMBINED_ALL, "r", encoding="utf-8") as f:
        base_lines = [l for l in f.read().splitlines() if l.strip()]

    with open(COMBINED_ALL_WITH_ENHSP, "r", encoding="utf-8") as f:
        enhsp_source_lines = [l for l in f.read().splitlines() if l.strip()]

    base_lines = [l for l in base_lines if not solver_of(l).startswith("ENHSP")]
    enhsp_lines = [l for l in enhsp_source_lines if solver_of(l).startswith("ENHSP")]

    shutil.copy(COMBINED_ALL, COMBINED_ALL + ".bak")

    with open("combined_all_1.log", "w", encoding="utf-8") as f:
        f.write("\n".join(base_lines + enhsp_lines) + "\n")

    print(f"Kept {len(base_lines)} non-ENHSP rows from {COMBINED_ALL}")
    print(f"Added {len(enhsp_lines)} ENHSP rows from {COMBINED_ALL_WITH_ENHSP}")
    print(f"Backup written to {COMBINED_ALL}.bak")


if __name__ == "__main__":
    main()
