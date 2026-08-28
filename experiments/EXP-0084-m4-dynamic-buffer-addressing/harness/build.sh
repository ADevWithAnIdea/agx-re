#!/bin/sh
# EXP-0084 harness build: compile this experiment's own harness sources
# (probe.m, splice_run.m) plus the read-only tools/shdump/shdump.m tool
# (never edited; its source hash is recorded by run.py) into $1/bin. Local M4
# only; no SSH anywhere.
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/probe" \
    "$HERE/harness/probe.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/splice_run" \
    "$HERE/harness/splice_run.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
echo "BUILT $OUT/probe $OUT/splice_run $OUT/shdump"
