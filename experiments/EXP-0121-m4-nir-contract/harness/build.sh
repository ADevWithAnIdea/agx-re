#!/bin/sh
# EXP-0121 harness build: compile OUR OWN read-only tool sources (tools/shdump,
# tools/agxtest) plus this experiment's own copied+adapted render harness
# (harness/fsrun.m, derived from experiments/EXP-0111-m4-fragment-semantics/
# harness/fsrun.m per SUBAGENT_BRIEF.md's explicit cross-experiment reuse
# allowance) into this experiment's work/bin. The read-only tools are never
# edited; their sources are hash-recorded by verify.py. Local M4 only; no SSH.
set -e
HARNESS="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HARNESS/../../.." && pwd)"
OUT="$1"
mkdir -p "$OUT"
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/shdump" \
    "$REPO/tools/shdump/shdump.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/agxrun" \
    "$REPO/tools/agxtest/agxrun.m" -framework Metal -framework Foundation
xcrun clang -fobjc-arc -Wno-deprecated-declarations -o "$OUT/fsrun" \
    "$HARNESS/fsrun.m" -framework Metal -framework Foundation
echo "BUILT $OUT/shdump $OUT/agxrun $OUT/fsrun"
