#!/bin/bash
# End-to-end submission test for IPC 2026 Numeric Agile Track.
#
# Tests both configurations:
#   - PATTY-BV  (Recipe       / run-lnp-agile  / --solver bitwuzla)
#   - PATTY-cvc5 (Recipe-patty / run-patty-agile / --solver cvc5)
#
# Usage:
#   ./test-submission.sh              # Apptainer mode (mirrors IPC environment)
#   ./test-submission.sh --local      # local venv mode (faster iteration, no container build)
#   ./test-submission.sh --bv-only    # only test PATTY-BV
#   ./test-submission.sh --patty-only # only test PATTY-cvc5

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
# Format: "domain_path problem_path label"
INSTANCES=(
    "files/fn-counters/domain.pddl  files/fn-counters/instances/instance_2.pddl   fn-counters/p2"
    "files/fn-counters/domain.pddl  files/fn-counters/instances/instance_4.pddl   fn-counters/p4"
    "files/tpp/domain.pddl          files/tpp/instances/p01.pddl                  tpp/p01"
    "files/tpp/domain.pddl          files/tpp/instances/p02.pddl                  tpp/p02"
    "files/sailing/domain.pddl      files/sailing/instances/instance_1_1_1229.pddl sailing/p1"
    "files/depots/domain.pddl       files/depots/instances/pfile1.pddl             depots/pfile1"
)

# ─── helpers ──────────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

record_result() {
    local status="$1" label="$2" config="$3" detail="$4"
    RESULTS+=("$status|$config|$label|$detail")
    if [[ "$status" == "PASS" ]]; then
        ((PASS++))
        green "  PASS  [$config] $label — $detail"
    elif [[ "$status" == "TIMEOUT" ]]; then
        ((FAIL++))
        yellow "  TIMEOUT  [$config] $label"
    else
        ((FAIL++))
        red "  FAIL  [$config] $label — $detail"
    fi
}

run_instance() {
    local cmd=("$@")
    local plan="${cmd[-1]}"   # last arg is always the plan output path
    local exit_code=0

    timeout "$TIMEOUT" "${cmd[@]}" >/tmp/patty_test.log 2>&1 || exit_code=$?

    if [[ $exit_code -eq 124 ]]; then
        echo "timeout"
    elif [[ ! -s "$plan" ]]; then
        echo "no-plan"
    else
        echo "ok:$(wc -l < "$plan") lines"
    fi
}

# ─── Apptainer mode ───────────────────────────────────────────────────────────
build_sif() {
    local recipe="$1" sif="$2"
    if [[ -f "$sif" ]]; then
        echo "  [cached] $sif"
        return
    fi
    echo "  Building $(basename "$sif") from $recipe ..."
    if apptainer build --fakeroot "$sif" "$recipe" 2>&1; then
        echo "  Built $sif"
    else
        # retry without --fakeroot (root environment)
        apptainer build "$sif" "$recipe"
        echo "  Built $sif"
    fi
}

test_apptainer() {
    local config="$1" sif="$2" extra_args="$3"
    echo ""
    echo "=== $config (Apptainer) ==="

    local TMPPLAN
    for entry in "${INSTANCES[@]}"; do
        read -r domain problem label <<< "$entry"
        domain="$SCRIPT_DIR/$domain"
        problem="$SCRIPT_DIR/$problem"
        TMPPLAN="$(mktemp /tmp/patty_plan_XXXXXX.pddl)"

        local result
        result=$(run_instance apptainer run "$sif" \
            -o "$domain" -f "$problem" --save-plan "$TMPPLAN" -v 0 $extra_args \
            "$TMPPLAN")

        rm -f "$TMPPLAN"
        case "$result" in
            ok:*)     record_result "PASS"    "$label" "$config" "${result#ok:}" ;;
            timeout)  record_result "TIMEOUT" "$label" "$config" "" ;;
            *)        record_result "FAIL"    "$label" "$config" "no plan produced" ;;
        esac
    done
}

# ─── local venv mode ──────────────────────────────────────────────────────────
test_local() {
    local config="$1" python_bin="$2" main_script="$3" extra_args="$4"
    echo ""
    echo "=== $config (local venv) ==="

    if [[ ! -x "$python_bin" ]]; then
        red "  SKIP — $python_bin not found. Run ./compile first."
        return
    fi

    local TMPPLAN
    for entry in "${INSTANCES[@]}"; do
        read -r domain problem label <<< "$entry"
        domain="$SCRIPT_DIR/$domain"
        problem="$SCRIPT_DIR/$problem"
        TMPPLAN="$(mktemp /tmp/patty_plan_XXXXXX.pddl)"

        local result
        result=$(run_instance "$python_bin" "$SCRIPT_DIR/$main_script" \
            -o "$domain" -f "$problem" --save-plan "$TMPPLAN" -v 0 $extra_args \
            "$TMPPLAN")

        rm -f "$TMPPLAN"
        case "$result" in
            ok:*)     record_result "PASS"    "$label" "$config" "${result#ok:}" ;;
            timeout)  record_result "TIMEOUT" "$label" "$config" "" ;;
            *)        record_result "FAIL"    "$label" "$config" "no plan produced" ;;
        esac
    done
}

# ─── main ─────────────────────────────────────────────────────────────────────
echo "IPC 2026 Numeric — Submission Test"
echo "Mode: $( $LOCAL && echo 'local venv' || echo 'Apptainer' )"
echo "Timeout per instance: ${TIMEOUT}s"

TMPDIR_SIFS="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_SIFS"' EXIT

if $LOCAL; then
    VENV_BIN="$SCRIPT_DIR/.venv/bin/python3"
    $RUN_BV    && test_local "PATTY-BV"   "$VENV_BIN" "main_bv.py" "--solver bitwuzla"
    $RUN_PATTY && test_local "PATTY-cvc5" "$VENV_BIN" "main.py"    "--solver cvc5"
else
    if ! command -v apptainer &>/dev/null; then
        red "ERROR: apptainer not found. Use --local for venv-based testing."
        exit 1
    fi

    echo ""
    echo "=== Building containers ==="
    $RUN_BV    && build_sif "$SCRIPT_DIR/Recipe"        "$TMPDIR_SIFS/patty-bv.sif"
    $RUN_PATTY && build_sif "$SCRIPT_DIR/Recipe-patty"  "$TMPDIR_SIFS/patty-cvc5.sif"

    $RUN_BV    && test_apptainer "PATTY-BV"    "$TMPDIR_SIFS/patty-bv.sif"   "--solver bitwuzla"
    $RUN_PATTY && test_apptainer "PATTY-cvc5"  "$TMPDIR_SIFS/patty-cvc5.sif" "--solver cvc5"
fi

# ─── summary ──────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
printf "%-12s %-20s %-18s %s\n" "STATUS" "CONFIG" "INSTANCE" "DETAIL"
echo "──────────────────────────────────────────"
for r in "${RESULTS[@]}"; do
    IFS='|' read -r status config label detail <<< "$r"
    printf "%-12s %-20s %-18s %s\n" "$status" "$config" "$label" "$detail"
done
echo "══════════════════════════════════════════"

if [[ $FAIL -eq 0 ]]; then
    green "All $PASS tests passed."
    exit 0
else
    red "$FAIL of $((PASS + FAIL)) tests failed."
    exit 1
fi
