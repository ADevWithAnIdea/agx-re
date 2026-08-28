#!/bin/sh
# Builds the (unmodified, pinned) tools/iotrace/iotrace.c interposer into this
# experiment's own harness/build/ directory. tools/iotrace itself is never
# modified (READ-ONLY per SUBAGENT_BRIEF.md); this only compiles it.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
repo=$(CDPATH= cd -- "$root/../.." && pwd)
src="$repo/tools/iotrace/iotrace.c"
out="$root/harness/build/iotrace.dylib"
mkdir -p "$root/harness/build"

want=4c8e1cedb9cbacd2e26c1699989337b95602a7c6beeb8823b19a71d1b55a3441
got=$(shasum -a 256 "$src" | awk '{print $1}')
if [ "$got" != "$want" ]; then
    echo "PINNED HASH MISMATCH for $src: want=$want got=$got" >&2
    exit 1
fi

clang -dynamiclib -o "$out" "$src" -framework IOKit -framework CoreFoundation
echo "built: $out"
