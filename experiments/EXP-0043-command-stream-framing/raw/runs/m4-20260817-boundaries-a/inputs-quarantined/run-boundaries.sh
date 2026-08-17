#!/bin/sh
# Adversarial follow-up at the segment rollover counts discovered in the first
# EXP-0043 run. Append-only and hard-timeout bounded.
set -eu

EXPERIMENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$EXPERIMENT_DIR/../.." && pwd)
RUN_ID=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-boundaries}
RUN_DIR="$EXPERIMENT_DIR/raw/runs/$RUN_ID"
BUILD_DIR="$EXPERIMENT_DIR/build/$RUN_ID"
TIMEOUT="$EXPERIMENT_DIR/analysis/hard_timeout.py"
ANALYZE="$EXPERIMENT_DIR/analysis/analyze.py"
FRAMING="$EXPERIMENT_DIR/analysis/framing_summary.py"

if [ -e "$RUN_DIR" ] || [ -e "$BUILD_DIR" ]; then
    echo "refusing to overwrite existing run: $RUN_ID" >&2
    exit 2
fi
mkdir -p "$RUN_DIR/cases" "$RUN_DIR/analysis" "$RUN_DIR/build-logs" \
    "$RUN_DIR/inputs" "$BUILD_DIR"

# Retain byte-exact authored inputs alongside this run.
cp "$EXPERIMENT_DIR/harness/framing.m" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/run-boundaries.sh" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/hard_timeout.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/analyze.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/capturelib.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/framing_summary.py" "$RUN_DIR/inputs/"
cp "$REPO_DIR/tools/iotrace/iotrace.c" "$RUN_DIR/inputs/"

{
    uname -srm
    sw_vers
    system_profiler SPHardwareDataType SPDisplaysDataType |
        grep -E '^[[:space:]]*(Model Name|Model Identifier|Chip|Total Number of Cores|Metal Support):'
    xcrun clang --version
    python3 --version
    git -C "$REPO_DIR" rev-parse HEAD
} > "$RUN_DIR/target.txt" 2> "$RUN_DIR/target.stderr"

python3 "$TIMEOUT" --seconds 90 -- xcrun clang -arch arm64e -dynamiclib \
    -o "$BUILD_DIR/iotrace.dylib" "$REPO_DIR/tools/iotrace/iotrace.c" \
    -framework IOKit -framework CoreFoundation \
    > "$RUN_DIR/build-logs/iotrace.stdout" 2> "$RUN_DIR/build-logs/iotrace.stderr"
python3 "$TIMEOUT" --seconds 90 -- xcrun clang -arch arm64e -fobjc-arc \
    -framework Metal -framework Foundation -o "$BUILD_DIR/framing" \
    "$EXPERIMENT_DIR/harness/framing.m" \
    > "$RUN_DIR/build-logs/framing.stdout" 2> "$RUN_DIR/build-logs/framing.stderr"

run_case() {
    label=$1
    shift
    case_dir="$RUN_DIR/cases/$label"
    mkdir -p "$case_dir/dumps"
    printf '%s\n' "$BUILD_DIR/framing $* --dump" > "$case_dir/command.txt"
    set +e
    IOTRACE_LOG="$case_dir/iotrace.log" \
    IOTRACE_DUMP_DIR="$case_dir/dumps" \
    IOTRACE_DUMP_PERSIG=1 IOTRACE_MAX_MAP=0x2000000 IOTRACE_MAX_STRUCT=0x100000 \
    DYLD_INSERT_LIBRARIES="$BUILD_DIR/iotrace.dylib" \
    python3 "$TIMEOUT" --seconds 180 -- "$BUILD_DIR/framing" "$@" --dump \
        > "$case_dir/stdout.txt" 2> "$case_dir/stderr.txt"
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$case_dir/exit-status.txt"
    dump_dir="$case_dir/dumps/dump00"
    if [ -d "$dump_dir" ]; then
        python3 "$ANALYZE" inventory "$dump_dir" > "$RUN_DIR/analysis/$label-inventory.txt"
        python3 "$ANALYZE" scan "$dump_dir" > "$RUN_DIR/analysis/$label-scan.txt"
        python3 "$FRAMING" "$dump_dir" > "$RUN_DIR/analysis/$label-framing.txt"
    fi
    [ "$rc" -eq 0 ] || echo "case $label retained failure rc=$rc" >&2
}

run_case compute_732 --mode compute --count 732 --alternate
run_case compute_733 --mode compute --count 733 --alternate
run_case compute_733_pad --mode compute --count 733 --alternate --pad 7 --pad-bytes 12288
run_case render_328 --mode render --count 328 --alternate
run_case render_329 --mode render --count 329 --alternate
run_case render_329_pad --mode render --count 329 --alternate --pad 7 --pad-bytes 12288

python3 "$ANALYZE" diff "$RUN_DIR/cases/compute_732/dumps/dump00" \
    "$RUN_DIR/cases/compute_733/dumps/dump00" > "$RUN_DIR/analysis/compute-boundary-diff.txt"
python3 "$ANALYZE" relocations "$RUN_DIR/cases/compute_733/dumps/dump00" \
    "$RUN_DIR/cases/compute_733_pad/dumps/dump00" > "$RUN_DIR/analysis/compute-link-relocation.txt"
python3 "$ANALYZE" diff "$RUN_DIR/cases/render_328/dumps/dump00" \
    "$RUN_DIR/cases/render_329/dumps/dump00" > "$RUN_DIR/analysis/render-boundary-diff.txt"
python3 "$ANALYZE" relocations "$RUN_DIR/cases/render_329/dumps/dump00" \
    "$RUN_DIR/cases/render_329_pad/dumps/dump00" > "$RUN_DIR/analysis/render-link-relocation.txt"

python3 "$EXPERIMENT_DIR/analysis/make_manifest.py" "$EXPERIMENT_DIR" --run-id "$RUN_ID" \
    > "$RUN_DIR/manifest-generation.txt"
echo "$RUN_ID"
