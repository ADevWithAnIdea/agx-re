#!/bin/sh
# EXP-0141 harness build: compile OUR OWN read-only tool sources
# (tools/shdump, tools/agxtest) into this experiment's work/<run>/bin.
# The tool sources are never edited; the runner hash-records them.
# Local M4 only; no SSH anywhere.
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun_persist" \
    "$REPO/tools/agxtest/agxrun_persist.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun" \
    "$REPO/tools/agxtest/agxrun.m" -framework Metal -framework Foundation
echo "BUILT $OUT/shdump $OUT/agxrun_persist $OUT/agxrun"
