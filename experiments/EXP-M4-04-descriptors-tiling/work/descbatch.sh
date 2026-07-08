#!/bin/bash
# descbatch.sh — run tvar across parameter variations under iotrace, print the
# extracted texture+sampler descriptor words for each. Clean-room: OWN-SHADER +
# DATA-TRACE of our own process. Compares M4 vs A18 documented values by eyeball.
set -u
cd "$(dirname "$0")"
D() { # D name args...
  local name="$1"; shift
  rm -rf "d_$name"
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="d_$name" DYLD_INSERT_LIBRARIES=./iotrace.dylib \
    ./tvar "$@" --dump >/dev/null 2>"d_$name.err"
  echo "### $name : tvar $*"
  python3 descx.py "d_$name" --words --tlen 0x20 --slen 0x08 2>/dev/null \
    | grep -E "TEXDESC|SAMPDESC|\+0000"
  echo
}
"$@"
