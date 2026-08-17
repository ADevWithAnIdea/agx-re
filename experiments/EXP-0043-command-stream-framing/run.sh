#!/bin/sh
# Clean EXP-0043 capture runner. Payload analysis is restricted to explicitly
# named, pre-classified command/state/descriptor BO files. No directory-wide BO
# payload scan and no address dereference/follow is performed.
set -eu

EXPERIMENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$EXPERIMENT_DIR/../.." && pwd)
RUN_SET=${RUN_SET:-full}
RUN_ID=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$RUN_SET}
RUN_DIR="$EXPERIMENT_DIR/raw/runs/$RUN_ID"
BUILD_DIR="$EXPERIMENT_DIR/build/$RUN_ID"
TIMEOUT="$EXPERIMENT_DIR/analysis/hard_timeout.py"
SAFE_FRAMING="$EXPERIMENT_DIR/analysis/safe_framing.py"
SAFE_FIELDS="$EXPERIMENT_DIR/analysis/safe_fields.py"
SAFE_COMPARE="$EXPERIMENT_DIR/analysis/safe_compare.py"

case "$RUN_SET" in full|boundaries) ;; *) echo "RUN_SET must be full or boundaries" >&2; exit 2;; esac
if [ -e "$RUN_DIR" ] || [ -e "$BUILD_DIR" ]; then
    echo "refusing to overwrite existing run: $RUN_ID" >&2
    exit 2
fi
mkdir -p "$RUN_DIR/cases" "$RUN_DIR/clean-analysis" "$RUN_DIR/build-logs" \
    "$RUN_DIR/inputs" "$BUILD_DIR"

cp "$EXPERIMENT_DIR/harness/framing.m" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/run.sh" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/hard_timeout.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/capturelib.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/safe_framing.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/safe_fields.py" "$RUN_DIR/inputs/"
cp "$EXPERIMENT_DIR/analysis/safe_compare.py" "$RUN_DIR/inputs/"
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

PYTHONDONTWRITEBYTECODE=1 python3 "$TIMEOUT" --seconds 90 -- xcrun clang -arch arm64e \
    -dynamiclib -o "$BUILD_DIR/iotrace.dylib" "$REPO_DIR/tools/iotrace/iotrace.c" \
    -framework IOKit -framework CoreFoundation \
    > "$RUN_DIR/build-logs/iotrace.stdout" 2> "$RUN_DIR/build-logs/iotrace.stderr"
PYTHONDONTWRITEBYTECODE=1 python3 "$TIMEOUT" --seconds 90 -- xcrun clang -arch arm64e \
    -fobjc-arc -framework Metal -framework Foundation -o "$BUILD_DIR/framing" \
    "$EXPERIMENT_DIR/harness/framing.m" \
    > "$RUN_DIR/build-logs/framing.stdout" 2> "$RUN_DIR/build-logs/framing.stderr"

analyze_explicit_va() {
    label=$1
    dump=$2
    kind=$3
    va=$4
    found=0
    for input_file in "$dump"/bo_*_va${va}_*.hex; do
        [ -f "$input_file" ] || continue
        found=$((found + 1))
        PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$EXPERIMENT_DIR/analysis" \
            python3 "$SAFE_FRAMING" --kind "$kind" "$input_file" \
            > "$RUN_DIR/clean-analysis/${label}-${kind}-va${va}-${found}.txt"
    done
}

run_case() {
    label=$1
    shift
    case_dir="$RUN_DIR/cases/$label"
    mkdir -p "$case_dir/dumps"
    printf '%s\n' "$BUILD_DIR/framing $* --dump" > "$case_dir/command.txt"
    set +e
    IOTRACE_LOG="$case_dir/iotrace.log" IOTRACE_DUMP_DIR="$case_dir/dumps" \
    IOTRACE_DUMP_PERSIG=1 IOTRACE_MAX_MAP=0x2000000 IOTRACE_MAX_STRUCT=0x100000 \
    DYLD_INSERT_LIBRARIES="$BUILD_DIR/iotrace.dylib" PYTHONDONTWRITEBYTECODE=1 \
    python3 "$TIMEOUT" --seconds 180 -- "$BUILD_DIR/framing" "$@" --dump \
        > "$case_dir/stdout.txt" 2> "$case_dir/stderr.txt"
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$case_dir/exit-status.txt"
    dump="$case_dir/dumps/dump00"
    [ -d "$dump" ] || return 0
    case "$label" in
        render_compute*) analyze_explicit_va "$label" "$dump" cdm 10000360000 ;;
        compute*|repeat_compute*|two_queues*)
            analyze_explicit_va "$label" "$dump" cdm 100000b8000
            analyze_explicit_va "$label" "$dump" cdm 10000158000 ;;
    esac
    case "$label" in
        render*|compute_render*|two_queues*)
            analyze_explicit_va "$label" "$dump" vdm 18000
            analyze_explicit_va "$label" "$dump" vdm 88000 ;;
    esac
}

if [ "$RUN_SET" = full ]; then
    run_case compute_1        --mode compute --count 1
    run_case compute_2        --mode compute --count 2 --alternate
    run_case compute_8        --mode compute --count 8 --alternate
    run_case compute_split_2  --mode compute-split --count 2 --alternate
    run_case compute_pad_2    --mode compute --count 2 --alternate --pad 7 --pad-bytes 12288
    run_case compute_1024     --mode compute --count 1024 --alternate
    run_case render_1         --mode render --count 1
    run_case render_2         --mode render --count 2 --alternate
    run_case render_8         --mode render --count 8 --alternate
    run_case render_split_2   --mode render-split --count 2 --alternate
    run_case render_pad_2     --mode render --count 2 --alternate --pad 7 --pad-bytes 12288
    run_case render_384       --mode render --count 384 --alternate
    run_case compute_render_2 --mode compute-render --count 2 --alternate
    run_case render_compute_2 --mode render-compute --count 2 --alternate
    run_case two_queues_2     --mode two-queues --count 2 --alternate
    run_case repeat_compute_3 --mode compute --count 2 --alternate --submits 3 --dump-each
else
    run_case compute_732      --mode compute --count 732 --alternate
    run_case compute_733      --mode compute --count 733 --alternate
    run_case compute_733_pad  --mode compute --count 733 --alternate --pad 7 --pad-bytes 12288
    run_case render_328       --mode render --count 328 --alternate
    run_case render_329       --mode render --count 329 --alternate
    run_case render_329_pad   --mode render --count 329 --alternate --pad 7 --pad-bytes 12288
fi

PYTHONDONTWRITEBYTECODE=1 python3 "$EXPERIMENT_DIR/analysis/audit_evidence.py" "$RUN_DIR" \
    > "$RUN_DIR/clean-analysis/evidence-audit.txt"
PYTHONDONTWRITEBYTECODE=1 python3 "$EXPERIMENT_DIR/analysis/make_manifest.py" \
    "$EXPERIMENT_DIR" --run-id "$RUN_ID"
echo "$RUN_ID"
