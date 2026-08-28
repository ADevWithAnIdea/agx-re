#!/bin/sh
# EXP-0108 harness build. Emits wtrace.dylib and probe into $1 (bin dir).
set -e
BIN="${1:?usage: build.sh <bindir>}"
mkdir -p "$BIN"
HERE="$(cd "$(dirname "$0")" && pwd)"
clang -dynamiclib -O2 -o "$BIN/wtrace.dylib" "$HERE/wtrace.c" -framework IOKit -framework CoreFoundation
clang -fobjc-arc -O2 -o "$BIN/probe" "$HERE/probe.m" -framework Metal -framework Foundation
