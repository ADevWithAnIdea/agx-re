#!/bin/sh
# cap.sh NAME [args...] — run iohello_compute under iotrace, dump BOs into maps_NAME/
NAME="$1"; shift
cd ~/cleanroom_work/EXP-M5-06
rm -rf "maps_$NAME"; mkdir -p "maps_$NAME"
IOTRACE_LOG="log_$NAME.txt" IOTRACE_DUMP_DIR="maps_$NAME" \
  DYLD_INSERT_LIBRARIES=../tools/iotrace/iotrace.dylib \
  ../tools/iotrace/iohello_compute "$@" --dump >"run_$NAME.txt" 2>&1
echo "cap $NAME done: $(grep -c '^CALL' log_$NAME.txt) calls, $(ls maps_$NAME | wc -l) maps"
grep -E '^VA|RESULT' "run_$NAME.txt"
