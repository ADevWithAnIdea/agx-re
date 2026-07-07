#!/bin/sh
# EXP-0027 occlusion/visibility-query capture matrix. Runs on the A18 device.
set -e
cd "$(dirname "$0")"
echo "=== build ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o qvar qvar.m 2>/dev/null
echo built
DYL=./iotrace.dylib
export IOTRACE_MAX_MAP=0x30000
run(){ label="$1"; shift; [ "$1" = "--" ] && shift
  d="capq/$label"; rm -rf "$d"; mkdir -p "$d"
  echo "--- $label : $* ---"
  IOTRACE_LOG="capq/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./qvar "$@" --dump > "capq/$label.stdout" 2>&1 || true
  grep -E '^(CONFIG|VA |VIS|SUBMIT|FAIL)' "capq/$label.stdout" || true
}
rm -rf capq; mkdir -p capq
run occ_none   -- --mode none
run occ_none2  -- --mode none
run occ_bool   -- --mode bool  --off 0
run occ_count  -- --mode count --off 0
run occ_bool8  -- --mode bool  --off 8
run occ_cnt16  -- --mode count --off 16
run occ_two    -- --mode two   --mode2 count --off 0 --off2 8

echo "=== analysis ==="
mkdir -p anq
for l in occ_none occ_none2 occ_bool occ_count occ_bool8 occ_cnt16 occ_two; do
  python3 dumpscan.py capq/$l --list > anq/list_$l.txt 2>&1 || true
done
python3 bodiff.py capq/occ_none capq/occ_none2 --maxlen 0x400 > anq/diff_det.txt 2>&1 || true
python3 bodiff.py capq/occ_none capq/occ_bool  --maxlen 0x400 > anq/diff_none_bool.txt 2>&1 || true
python3 bodiff.py capq/occ_bool capq/occ_count --maxlen 0x400 > anq/diff_bool_count.txt 2>&1 || true
python3 bodiff.py capq/occ_bool capq/occ_bool8 --maxlen 0x400 > anq/diff_bool_off.txt 2>&1 || true
python3 bodiff.py capq/occ_count capq/occ_cnt16 --maxlen 0x400 > anq/diff_count_off.txt 2>&1 || true
python3 bodiff.py capq/occ_bool capq/occ_two   --maxlen 0x400 > anq/diff_bool_two.txt 2>&1 || true
# find the visBuf VA everywhere
for l in occ_bool occ_count occ_two; do
  vb=$(grep 'VA visBuf' capq/$l.stdout | grep -oE '0x[0-9a-f]+' | head -1)
  echo "== $l visBuf=$vb ==" >> anq/visptr.txt
  python3 dumpscan.py capq/$l --u64 $vb >> anq/visptr.txt 2>&1 || true
done
echo done; ls anq
