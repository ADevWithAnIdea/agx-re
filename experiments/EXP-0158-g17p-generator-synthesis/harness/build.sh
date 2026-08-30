#!/bin/sh
# EXP-0158 harness build (G17P): compile OUR OWN read-only tool sources
# (tools/shdump, tools/agxtest) into this experiment's work/bin, ON THE TARGET,
# from source, every run. The tools are never edited; their sources are
# hash-recorded by the runner. Rebuilding rather than copying a binary is the
# NEO-TARGET-BRIEF.md instruction and also means the binaries are demonstrably
# the ones this repository's committed source produces.
set -e
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun" \
    "$REPO/tools/agxtest/agxrun.m" -framework Metal -framework Foundation
echo "BUILT $OUT/shdump $OUT/agxrun"
