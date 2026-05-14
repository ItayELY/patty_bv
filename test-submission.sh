#!/bin/bash
# End-to-end submission test for IPC 2026 Numeric Agile Track.
#
# Tests both configurations:
#   - PATTY-BV   (Recipe       / --solver bitwuzla)
#   - PATTY-z3   (Recipe-patty / --solver z3)
#
# Usage:
#   ./test-submission.sh              # Apptainer mode (mirrors IPC environment)
#   ./test-submission.sh --local      # local .venv mode (no container build needed)
#   ./test-submission.sh --bv-only    # only test PATTY-BV
#   ./test-submission.sh --patty-only # only test PATTY-z3

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── options ──────────────────────────────────────────────────────────────────
LOCAL=false
RUN_BV=true
RUN_PATTY=true
for arg in "$@"; do
    case "$arg" in
        --local)       LOCAL=true ;;
        --bv-only)     RUN_PATTY=false ;;
        --patty-only)  RUN_BV=false ;;
    esac
done

TIMEOUT=120   # seconds per instance
PASS=0
FAIL=0
RESULTS=()

# ─── test instances ────────────────────────────────────────────────────────────
# Format: "domain_path  problem_path  label"
INSTANCES=(
    "files/fn-counters/domain.pddl   files/fn-counters/instances/instance_2.pddl    fn-counters/p2"
    "files/fn-counters/domain.pddl   files/fn-counters/instances/instance_4.pddl    fn-counters/p4"
    "files/tpp/domain.pddl           files/tpp/instances/p01.pddl                   tpp/p01"
    "files/tpp/domain.pddl           files/tpp/instances/p02.pddl                   tpp/p02"
    "files/sailing/domain.pddl       files/sailing/instances/instance_1_1_1229.pddl sailing/p1"
    "files/depots/domain.pddl        files/depots/instances/pfile1.pddl              depots/pfile1"
)

# ─── helpers ──────────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

record_result() {
    local status="$1" config="$2" label="$3" detail="$4"
    RESULTS+=("$status|$config|$label|$detail")
    if [[ "$status" == "PASS" ]]; then
        ((PASS++));  green   "  PASS     [$config] $label — $detail"
    elif [[ "$status" == "TIMEOUT" ]]; then
        ((FAIL++));  yellow  "  TIMEOUT  [$config] $label"
    else
        ((FAIL++));  red     "  FAIL     [$config] $label — $detail"
    fi
}

# run_instance PLAN_FILE CMD [ARGS...]
# Runs CMD with a timeout; echoes "ok:N lines", "timeout", or "no-plan".
run_instance() {
    local plan="$1"; shift
    local exit_code=0
    timeout "$TIMEOUT" "$@" >/tmp/patty_test.log 2>&1 || exit_code=$?
    if   [[ $exit_code -eq 124 ]];  then echo "timeout"
    elif [[ ! -s "$plan" ]];        then echo "no-plan"
    else echo "ok:$(wc -l < "$plan") lines"
    fi
}

# ─── Apptainer helpers ────────────────────────────────────────────────────────
# Build a sandbox directory (no FUSE/squashfuse required, works inside Docker).
build_sandbox() {
    local recipe="$1" sandbox="$2"
    echo "  Building sandbox from $(basename "$recipe") ..."
    if ! apptainer build --sandbox "$sandbox" "$recipe"; then
        red "  ERROR: failed to build sandbox from $recipe"
        exit 1
    fi
    echo "  Built $sandbox"
}

test_apptainer() {
    local config="$1" sandbox="$2"
    echo ""
    echo "=== $config (Apptainer) ==="
    for entry in "${INSTANCES[@]}"; do
        read -r domain problem label <<< "$entry"
        local plan; plan="$(mktemp /tmp/patty_plan_XXXXXX.pddl)"
        # --bind exposes the project files inside the container at the same path
        # shellcheck disable=SC2086
        local result; result=$(run_instance "$plan" \
            apptainer run --bind "$SCRIPT_DIR:$SCRIPT_DIR" "$sandbox" \
                "$SCRIPT_DIR/$domain" "$SCRIPT_DIR/$problem" "$plan")
        rm -f "$plan"
        case "$result" in
            ok:*)    record_result "PASS"    "$config" "$label" "${result#ok:}" ;;
            timeout) record_result "TIMEOUT" "$config" "$label" "" ;;
            *)       record_result "FAIL"    "$config" "$label" "no plan produced" ;;
        esac
    done
}

# ─── local venv helpers ───────────────────────────────────────────────────────
test_local() {
    local config="$1" main_script="$2" extra_args="$3"
    local python_bin="$SCRIPT_DIR/.venv/bin/python3"
    echo ""
    echo "=== $config (local venv) ==="
    if [[ ! -x "$python_bin" ]]; then
        red "  SKIP — .venv not found. Run ./compile first."
        return
    fi
    for entry in "${INSTANCES[@]}"; do
        read -r domain problem label <<< "$entry"
        local plan; plan="$(mktemp /tmp/patty_plan_XXXXXX.pddl)"
        # shellcheck disable=SC2086
        local result; result=$(run_instance "$plan" \
            "$python_bin" "$SCRIPT_DIR/$main_script" \
                -o "$SCRIPT_DIR/$domain" \
                -f "$SCRIPT_DIR/$problem" \
                --save-plan "$plan" \
                -v 0 $extra_args)
        rm -f "$plan"
        case "$result" in
            ok:*)    record_result "PASS"    "$config" "$label" "${result#ok:}" ;;
            timeout) record_result "TIMEOUT" "$config" "$label" "" ;;
            *)       record_result "FAIL"    "$config" "$label" "no plan produced" ;;
        esac
    done
}

# ─── main ─────────────────────────────────────────────────────────────────────
echo "IPC 2026 Numeric — Submission Test"
echo "Mode: $( $LOCAL && echo 'local venv' || echo 'Apptainer (sandbox)' )"
echo "Timeout per instance: ${TIMEOUT}s"

if $LOCAL; then
    $RUN_BV    && test_local "PATTY-BV" "main_bv.py" "--solver bitwuzla"
    $RUN_PATTY && test_local "PATTY-z3" "main.py"    "--solver z3"
else
    if ! command -v apptainer &>/dev/null; then
        red "ERROR: apptainer not found. Use --local for venv-based testing."
        exit 1
    fi

    TMPDIR_BOXES="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR_BOXES"' EXIT
    BV_BOX="$TMPDIR_BOXES/patty-bv"
    PATTY_BOX="$TMPDIR_BOXES/patty-z3"

    echo ""
    echo "=== Building containers ==="
    $RUN_BV    && build_sandbox "$SCRIPT_DIR/Recipe"        "$BV_BOX"
    $RUN_PATTY && build_sandbox "$SCRIPT_DIR/Recipe-patty"  "$PATTY_BOX"

    $RUN_BV    && test_apptainer "PATTY-BV" "$BV_BOX"
    $RUN_PATTY && test_apptainer "PATTY-z3" "$PATTY_BOX"
fi

# ─── summary ──────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
printf "%-10s %-14s %-20s %s\n" "STATUS" "CONFIG" "INSTANCE" "DETAIL"
echo "──────────────────────────────────────────────────"
for r in "${RESULTS[@]}"; do
    IFS='|' read -r status config label detail <<< "$r"
    printf "%-10s %-14s %-20s %s\n" "$status" "$config" "$label" "$detail"
done
echo "══════════════════════════════════════════════════"

if [[ $FAIL -eq 0 ]]; then
    green "All $PASS tests passed."
    exit 0
else
    red "$FAIL of $((PASS + FAIL)) tests failed."
    exit 1
fi
