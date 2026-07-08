#!/bin/bash
# run.sh — capture MRT command-stream traces for attachment counts 1..8 and mixed formats.
# CLEAN-ROOM: DATA-TRACE (interpose IOKit, dump our own process's GPU BOs) + OWN-SHADER.
# No Apple binary disassembled.  Runs on the LOCAL Apple M4 host.
set -u
cd "$(dirname "$0")"

cap () {  # cap LABEL ARGS...
  local label="$1"; shift
  local d="caps/$label"
  mkdir -p "$d"
  IOTRACE_MAX_MAP=0x8000 IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=./iotrace.dylib ./mrtvar "$@" --dump > "$d.out" 2>&1
  echo "== $label: $(grep -h 'status=' "$d.out" | tail -1)  $(grep -c CB_ERROR "$d.out") CB_ERROR  bo=$(ls "$d"/*.hex 2>/dev/null | wc -l | tr -d ' ')"
}

rm -rf caps; mkdir -p caps

# attachment-count sweep, all bgra8
cap mrt1 --n 1
cap mrt2 --n 2
cap mrt3 --n 3
cap mrt4 --n 4
cap mrt5 --n 5
cap mrt6 --n 6
cap mrt7 --n 7
cap mrt8 --n 8

# mixed per-RT formats (float-writable only)
cap mixA --n 8 --fmts bgra8,rgba8,r8,rg8,r16f,rg16f,r32f,rgba16f
cap mixB --n 8 --fmts rgba32f,rgb10a2,r32f,rgba16f,bgra8,r8,rg16f,rg8
cap mixC --n 4 --fmts r32f,bgra8,rgba16f,rgb10a2

echo "done"
