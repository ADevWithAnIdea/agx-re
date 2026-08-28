#!/bin/sh
# EXP-0096 harness build: compiles the READ-ONLY tool sources
# (tools/shdump/shdump.m, tools/agxtest/agxrun.m) plus this experiment's own
# harness/tgbudget.m into $1 (a fresh bin dir). Command Line Tools only, no
# `metal` CLI. Mirrors ../EXP-0082-m4-mem-offset-semantics/harness/build.sh
# with tgbudget.m added.
set -eu
BIN_DIR="$1"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
mkdir -p "$BIN_DIR"
clang -fobjc-arc -framework Metal -framework Foundation \
    -o "$BIN_DIR/shdump" "$REPO/tools/shdump/shdump.m"
clang -fobjc-arc -framework Metal -framework Foundation \
    -o "$BIN_DIR/agxrun" "$REPO/tools/agxtest/agxrun.m"
clang -fobjc-arc -framework Metal -framework Foundation \
    -o "$BIN_DIR/tgbudget" "$HERE/tgbudget.m"
echo "built: $BIN_DIR/shdump $BIN_DIR/agxrun $BIN_DIR/tgbudget"
