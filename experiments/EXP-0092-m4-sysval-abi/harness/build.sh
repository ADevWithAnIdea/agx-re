#!/bin/sh
# EXP-0092 harness build: compile OUR OWN read-only tool sources (tools/shdump,
# tools/agxtest) AND our own new harness sources (agxvdraw, agxcdispatch) into
# this experiment's work/bin. tools/* are never edited; their sources are
# hash-recorded by the runner. Local M4 only; no SSH anywhere.
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun" \
    "$REPO/tools/agxtest/agxrun.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxvdraw" \
    "$HERE/agxvdraw.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxcdispatch" \
    "$HERE/agxcdispatch.m" -framework Metal -framework Foundation
echo "BUILT $OUT/shdump $OUT/agxrun $OUT/agxvdraw $OUT/agxcdispatch"
