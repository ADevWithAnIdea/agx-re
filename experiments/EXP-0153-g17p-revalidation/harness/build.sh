#!/bin/bash
# EXP-0153 device-side build. Run ON THE NEO (G17P) from ~/agxre/EXP-0153.
# Rebuilds the runner binaries from OUR OWN sources in ~/agxre/tools rather
# than copying binaries, per NEO-TARGET-BRIEF.
set -euo pipefail
TOOLS="${AGX_TOOLS:-$HOME/agxre/tools}"
BIN="$(cd "$(dirname "$0")/.." && pwd)/bin"
mkdir -p "$BIN"
clang -fobjc-arc -framework Metal -framework Foundation -O2 \
      -o "$BIN/shdump"         "$TOOLS/shdump/shdump.m"
clang -fobjc-arc -framework Metal -framework Foundation -O2 \
      -o "$BIN/agxrun_persist" "$TOOLS/agxtest/agxrun_persist.m"
shasum -a 256 "$BIN/shdump" "$BIN/agxrun_persist"
echo "build ok -> $BIN"
