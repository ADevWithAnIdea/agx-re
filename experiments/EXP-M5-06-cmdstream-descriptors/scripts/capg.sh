#!/bin/sh
# capg.sh BIN NAME [args...]
BIN="$1"; NAME="$2"; shift 2
cd ~/cleanroom_work/EXP-M5-06
rm -rf "m_$NAME"; mkdir -p "m_$NAME"
IOTRACE_LOG="l_$NAME.txt" IOTRACE_DUMP_DIR="m_$NAME" \
  DYLD_INSERT_LIBRARIES=../tools/iotrace/iotrace.dylib \
  ./$BIN "$@" --dump >"r_$NAME.txt" 2>&1
S=$(grep -oE 'STATUS=[0-9]+' r_$NAME.txt)
echo "$NAME: $S $(grep -oE 'COMPILE_FAIL.*|PIPELINE_FAIL.*' r_$NAME.txt | head -1)"
