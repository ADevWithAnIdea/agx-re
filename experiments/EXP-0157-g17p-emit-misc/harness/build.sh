#!/bin/bash
# EXP-0157 device-side build. Run ON THE NEO (G17P) from ~/agxre/EXP-0157.
# Binaries are rebuilt from OUR OWN sources rather than copied (NEO-TARGET-BRIEF).
# `agxrun_persist_as` is built from THIS experiment's harness copy; the shared
# tools/agxtest/agxrun_persist.m is left untouched so concurrent sibling
# experiments keep building.
set -euo pipefail
TOOLS="${AGX_TOOLS:-$HOME/agxre/tools}"
EXPDIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$EXPDIR/bin"
mkdir -p "$BIN"
clang -fobjc-arc -framework Metal -framework Foundation -O2 -Wno-deprecated-declarations \
      -o "$BIN/shdump"             "$TOOLS/shdump/shdump.m"
clang -fobjc-arc -framework Metal -framework Foundation -O2 -Wno-deprecated-declarations \
      -o "$BIN/agxrun_persist"     "$TOOLS/agxtest/agxrun_persist.m"
clang -fobjc-arc -framework Metal -framework Foundation -O2 -Wno-deprecated-declarations \
      -o "$BIN/agxrun_persist_as"  "$EXPDIR/harness/agxrun_persist_as.m"
shasum -a 256 "$BIN"/shdump "$BIN"/agxrun_persist "$BIN"/agxrun_persist_as
echo "build ok -> $BIN"
