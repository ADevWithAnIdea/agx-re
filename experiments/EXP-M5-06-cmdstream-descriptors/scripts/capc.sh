#!/bin/sh
NAME="$1"; shift
cd ~/cleanroom_work/EXP-M5-06
rm -rf "maps_$NAME"; mkdir -p "maps_$NAME"
IOTRACE_LOG="log_$NAME.txt" IOTRACE_DUMP_DIR="maps_$NAME" \
  DYLD_INSERT_LIBRARIES=../tools/iotrace/iotrace.dylib \
  ./cvar_compute "$@" --dump >"run_$NAME.txt" 2>&1
echo "== $NAME =="; grep -E 'DEVICE|STATUS|COMPILE_FAIL|PIPELINE_FAIL' run_$NAME.txt
