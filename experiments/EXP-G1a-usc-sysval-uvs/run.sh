#!/bin/sh
# EXP-G1a run script (runs ON the device under ~/cleanroom_work/exp_g1a/).
# Captures the USC program (0x10000130000), varying-linkage BO (0x10000120000),
# VDM (0x18000), FF-state (0x58000), attribute table (0x10000100000), attachment
# (0x10000110000) and code BO (0x10000000000) for a sweep over bound-resource
# counts and varying counts/orders.  DATA-TRACE via the existing iotrace.dylib.
set -e
DYL=./iotrace.dylib
BIN=./uvar
run() {  # run <tag> <args...>
  tag="$1"; shift
  echo "=== $tag : $* ==="
  IOTRACE_LOG="log_$tag.txt" IOTRACE_DUMP_DIR="cap_$tag" \
    DYLD_INSERT_LIBRARIES="$DYL" "$BIN" "$@" --dump 2>&1 | \
    grep -E '^(CONFIG|VA|SUBMIT|PIXEL|.*FAIL)' || true
}

# ---- G1-a: binding-word grammar (vary ONE resource type at a time) ----
run base    --vary 1
run tex1    --vary 1 --ftex 1 --fsmp 1
run tex2    --vary 1 --ftex 2 --fsmp 1
run tex3    --vary 1 --ftex 3 --fsmp 1
run smp1    --vary 1 --ftex 1 --fsmp 1
run smp2    --vary 1 --ftex 1 --fsmp 2
run smp3    --vary 1 --ftex 1 --fsmp 3
run fbuf1   --vary 1 --fbuf 1
run fbuf2   --vary 1 --fbuf 2
run fbuf3   --vary 1 --fbuf 3
run vbuf1   --vary 1 --vbuf 1
run vbuf2   --vary 1 --vbuf 2
run texsmpbuf --vary 1 --ftex 2 --fsmp 2 --fbuf 1

# ---- G1-c: sysval probing ----
run vid     --vary 1 --vid
run iid     --vary 1 --iid
run vidiid  --vary 1 --vid --iid

# ---- G1-e: varying count / linkage ----
run vary0   --vary 0
run vary1   --vary 1
run vary2   --vary 2
run vary3   --vary 3
run vary4   --vary 4
run vary8   --vary 8

# ---- G1-e HW validation: echo a chosen varying (reorder proof) ----
run vout0   --vary 3 --vout 0
run vout1   --vary 3 --vout 1
run vout2   --vary 3 --vout 2

echo "ALL DONE"
