#!/bin/sh
# EXP-0027 timestamp / counter-sample capture matrix. Runs on the A18 device.
set -e
cd "$(dirname "$0")"
echo "=== build ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o tvar tvar.m 2>/dev/null
echo built
DYL=./iotrace.dylib
export IOTRACE_MAX_MAP=0x30000
run(){ label="$1"; shift; [ "$1" = "--" ] && shift
  d="capt/$label"; rm -rf "$d"; mkdir -p "$d"
  echo "--- $label : $* ---"
  IOTRACE_LOG="capt/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./tvar "$@" --dump > "capt/$label.stdout" 2>&1 || true
  grep -E '^(CONFIG|VA |TS|SUBMIT|COUNTERSET|FAIL|NO_)' "capt/$label.stdout" || true
}
rm -rf capt; mkdir -p capt
run cnone    -- --mode none
run csample  -- --mode csample
run rnone    -- --mode rnone
run rnone2   -- --mode rnone
run rsample  -- --mode rsample

echo "=== analysis ==="
mkdir -p ant
for l in cnone csample rnone rnone2 rsample; do
  python3 dumpscan.py capt/$l --list > ant/list_$l.txt 2>&1 || true
done
python3 bodiff.py capt/rnone capt/rnone2   --maxlen 0x800 > ant/diff_det.txt 2>&1 || true
python3 bodiff.py capt/rnone capt/rsample  --maxlen 0x800 > ant/diff_rnone_rsample.txt 2>&1 || true
# scan for the resolved timestamp values in the captured BOs (find the write destination)
for l in csample rsample; do
  echo "== $l TS scan ==" >> ant/tsscan.txt
  for v in $(grep -oE 'TS\[[0-9]\]=[0-9]+' capt/$l.stdout | grep -oE '[0-9]+$'); do
    echo "-- needle $v --" >> ant/tsscan.txt
    python3 dumpscan.py capt/$l --u64 $v >> ant/tsscan.txt 2>&1 || true
  done
done
echo done; ls ant
