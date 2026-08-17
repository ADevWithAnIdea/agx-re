#!/bin/sh
# Append-only M4 DATA-TRACE runner for EXP-0043. Every external build/probe has
# a hard timeout. Generated raw evidence is never overwritten.
set -eu

EXPERIMENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$EXPERIMENT_DIR/../.." && pwd)
RUN_ID=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}
RUN_DIR="$EXPERIMENT_DIR/raw/runs/$RUN_ID"
BUILD_DIR="$EXPERIMENT_DIR/build/$RUN_ID"
TIMEOUT="$EXPERIMENT_DIR/analysis/hard_timeout.py"
ANALYZE="$EXPERIMENT_DIR/analysis/analyze.py"

if [ -e "$RUN_DIR" ] || [ -e "$BUILD_DIR" ]; then
    echo "refusing to overwrite existing run: $RUN_ID" >&2
    exit 2
fi
mkdir -p "$RUN_DIR/cases" "$RUN_DIR/analysis" "$RUN_DIR/build-logs" "$BUILD_DIR"

# Sanitized target/tool identity: intentionally excludes serial, UUID, UDID,
# activation-lock, user name, and executable paths.
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
    seconds=$2
    shift 2
    case_dir="$RUN_DIR/cases/$label"
    mkdir -p "$case_dir/dumps"
    printf '%s\n' "$BUILD_DIR/framing $* --dump" > "$case_dir/command.txt"
    set +e
    IOTRACE_LOG="$case_dir/iotrace.log" \
    IOTRACE_DUMP_DIR="$case_dir/dumps" \
    IOTRACE_DUMP_PERSIG=1 \
    IOTRACE_MAX_MAP=0x2000000 \
    IOTRACE_MAX_STRUCT=0x100000 \
    DYLD_INSERT_LIBRARIES="$BUILD_DIR/iotrace.dylib" \
    python3 "$TIMEOUT" --seconds "$seconds" -- "$BUILD_DIR/framing" "$@" --dump \
        > "$case_dir/stdout.txt" 2> "$case_dir/stderr.txt"
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$case_dir/exit-status.txt"
    if [ "$rc" -ne 0 ]; then
        echo "case $label retained failure rc=$rc" >&2
    fi
    for dump_dir in "$case_dir"/dumps/dump*; do
        [ -d "$dump_dir" ] || continue
        dump_name=$(basename "$dump_dir")
        python3 "$ANALYZE" inventory "$dump_dir" \
            > "$RUN_DIR/analysis/${label}-${dump_name}-inventory.txt" 2>&1 || true
        python3 "$ANALYZE" scan "$dump_dir" \
            > "$RUN_DIR/analysis/${label}-${dump_name}-scan.txt" 2>&1 || true
    done
}

run_case compute_1        120 --mode compute --count 1
run_case compute_2        120 --mode compute --count 2 --alternate
run_case compute_8        120 --mode compute --count 8 --alternate
run_case compute_split_2  120 --mode compute-split --count 2 --alternate
run_case compute_pad_2    120 --mode compute --count 2 --alternate --pad 7 --pad-bytes 12288
run_case compute_1024     180 --mode compute --count 1024 --alternate

run_case render_1         120 --mode render --count 1
run_case render_2         120 --mode render --count 2 --alternate
run_case render_8         120 --mode render --count 8 --alternate
run_case render_split_2   120 --mode render-split --count 2 --alternate
run_case render_pad_2     120 --mode render --count 2 --alternate --pad 7 --pad-bytes 12288
run_case render_384       180 --mode render --count 384 --alternate

run_case compute_render_2 150 --mode compute-render --count 2 --alternate
run_case render_compute_2 150 --mode render-compute --count 2 --alternate
run_case two_queues_2     150 --mode two-queues --count 2 --alternate
run_case repeat_compute_3 180 --mode compute --count 2 --alternate --submits 3 --dump-each

pair_report() {
    name=$1
    a=$2
    b=$3
    python3 "$ANALYZE" diff "$a" "$b" > "$RUN_DIR/analysis/$name-diff.txt"
    python3 "$ANALYZE" relocations "$a" "$b" > "$RUN_DIR/analysis/$name-relocations.txt"
}

pair_report compute-1-vs-2 \
    "$RUN_DIR/cases/compute_1/dumps/dump00" "$RUN_DIR/cases/compute_2/dumps/dump00"
pair_report compute-2-vs-8 \
    "$RUN_DIR/cases/compute_2/dumps/dump00" "$RUN_DIR/cases/compute_8/dumps/dump00"
pair_report compute-same-vs-split \
    "$RUN_DIR/cases/compute_2/dumps/dump00" "$RUN_DIR/cases/compute_split_2/dumps/dump00"
pair_report compute-relocation \
    "$RUN_DIR/cases/compute_2/dumps/dump00" "$RUN_DIR/cases/compute_pad_2/dumps/dump00"
pair_report render-1-vs-2 \
    "$RUN_DIR/cases/render_1/dumps/dump00" "$RUN_DIR/cases/render_2/dumps/dump00"
pair_report render-2-vs-8 \
    "$RUN_DIR/cases/render_2/dumps/dump00" "$RUN_DIR/cases/render_8/dumps/dump00"
pair_report render-same-vs-split \
    "$RUN_DIR/cases/render_2/dumps/dump00" "$RUN_DIR/cases/render_split_2/dumps/dump00"
pair_report render-relocation \
    "$RUN_DIR/cases/render_2/dumps/dump00" "$RUN_DIR/cases/render_pad_2/dumps/dump00"
pair_report mixed-order \
    "$RUN_DIR/cases/compute_render_2/dumps/dump00" "$RUN_DIR/cases/render_compute_2/dumps/dump00"
pair_report repeat-submit-0-vs-1 \
    "$RUN_DIR/cases/repeat_compute_3/dumps/dump00" "$RUN_DIR/cases/repeat_compute_3/dumps/dump01"
pair_report repeat-submit-1-vs-2 \
    "$RUN_DIR/cases/repeat_compute_3/dumps/dump01" "$RUN_DIR/cases/repeat_compute_3/dumps/dump02"

python3 "$EXPERIMENT_DIR/analysis/make_manifest.py" "$EXPERIMENT_DIR" --run-id "$RUN_ID" \
    > "$RUN_DIR/manifest-generation.txt"
echo "$RUN_ID"
