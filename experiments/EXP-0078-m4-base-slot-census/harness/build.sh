#!/bin/sh
# EXP-0078 harness build: compile OUR OWN harness against the public Metal
# API, and compile the read-only tool source tools/shdump/shdump.m into this
# experiment's work tree. tools/* are never edited; their sources are
# hash-recorded by the runner. Local M4 only; no SSH anywhere.
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/probe" \
    "$REPO/experiments/EXP-0078-m4-base-slot-census/harness/probe.m" \
    -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
echo "BUILT $OUT/probe $OUT/shdump"
