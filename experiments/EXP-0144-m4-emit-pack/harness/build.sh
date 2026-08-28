#!/bin/sh
# EXP-0144 harness build: compile OUR OWN read-only tool sources
# (tools/shdump, tools/agxtest) into this experiment's work/bin. The tools are
# never edited; their sources are hash-recorded by the runner. Local M4 only;
# no SSH anywhere. (Pattern from EXP-0119/EXP-0099 build.sh.)
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun_persist" \
    "$REPO/tools/agxtest/agxrun_persist.m" -framework Metal -framework Foundation
echo "BUILT $OUT/shdump $OUT/agxrun_persist"
