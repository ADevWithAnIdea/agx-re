#!/bin/sh
# EXP-0119 harness build: compile OUR OWN read-only tool sources
# (tools/shdump, tools/agxtest) into this experiment's work/bin. The tools
# are never edited; their sources are hash-recorded by the runner. Local M4
# only; no SSH anywhere. (Verbatim pattern from EXP-0090/EXP-0099.)
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun" \
    "$REPO/tools/agxtest/agxrun.m" -framework Metal -framework Foundation
# fsrun: EXP-0126's OWN authored copy (derived from EXP-0111/EXP-0091's fsrun.m, itself a
# superset of tools/agxtest/agxrender.m), patched to remove all NSTemporaryDirectory/system-/tmp
# usage (see harness/fsrun.m's inline comment) -- built from THIS experiment's own harness/,
# never from tools/.
HERE_HARNESS="$(cd "$(dirname "$0")" && pwd)"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/fsrun" \
    "$HERE_HARNESS/fsrun.m" -framework Metal -framework Foundation
echo "BUILT $OUT/shdump $OUT/agxrun $OUT/fsrun"
