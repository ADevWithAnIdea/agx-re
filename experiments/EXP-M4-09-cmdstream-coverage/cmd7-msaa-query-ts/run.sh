#!/bin/bash
# run.sh — CMD-7 reproducible harness: MSAA sample-count breadth, occlusion offset
# breadth, GPU timestamps. LOCAL Apple M4 (this host). Public Metal API + iotrace
# DATA-TRACE only. Our own MSL. No Apple binary inspected.
set -e
cd "$(dirname "$0")"

echo "== build =="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
for m in ovar qvar tvar sctest pipe8; do
  clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o "$m" "$m.m"
done
mkdir -p caps

DYL=./iotrace.dylib
CAP='IOTRACE_MAX_MAP=0x800 IOTRACE_LOG=/dev/null'

echo "== (a) MSAA sample-count capability =="
./sctest > caps/sctest.out 2>&1 || true      # supportsTextureSampleCount + tex/pipe at 1/2/4/8
./pipe8  > caps/pipe8.out  2>&1 || true       # pipeline rasterSampleCount=8 in isolation
for N in 1 2 4; do
  d=caps/msaa$N; mkdir -p "$d"
  env $CAP IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL ./ovar --msaa $N --dump > "$d.out" 2>&1
done

echo "== (b) occlusion offset/mode breadth =="
for o in 0 8 16 64 256 1024 4096; do
  d=caps/q_count_off$o; mkdir -p "$d"
  env $CAP IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL ./qvar --mode count --off $o --dump > "$d.out" 2>&1
done
for o in 0 8; do
  d=caps/q_bool_off$o; mkdir -p "$d"
  env $CAP IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL ./qvar --mode bool --off $o --dump > "$d.out" 2>&1
done

echo "== (c) timestamps =="
./tvar --mode correlate > caps/tv_correlate.out 2>&1
./tvar --mode csample   > caps/tv_csample.out   2>&1
./tvar --mode rsample   > caps/tv_rsample.out   2>&1

echo "== done; see caps/ and RESULTS.md =="
