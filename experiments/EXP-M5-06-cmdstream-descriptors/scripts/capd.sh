#!/bin/sh
NAME="$1"; shift
cd ~/cleanroom_work/EXP-M5-06
rm -rf "mapsd_$NAME"; mkdir -p "mapsd_$NAME"
IOTRACE_LOG="logd_$NAME.txt" IOTRACE_DUMP_DIR="mapsd_$NAME" \
  DYLD_INSERT_LIBRARIES=../tools/iotrace/iotrace.dylib \
  ../tools/iotrace/iohello_draw "$@" --dump >"rund_$NAME.txt" 2>&1
echo "== draw $NAME =="; grep -cE '^CALL' logd_$NAME.txt; grep -E '^OPEN|PIXEL' rund_$NAME.txt
