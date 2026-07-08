#!/bin/sh
# capdims.sh — DESC-2: 14-bit width/height on non-2D types + depth/arrayLen field.
# Sweeps 2DArray/3D/Cube large dims and the PBE (storage-image) alternate split.
# Clean-room: DATA-TRACE of our own process.
set -u
DYL=./iotrace.dylib
OUT=${1:-../raw/dims_capture.txt}
: > "$OUT"

cap() { # label + tvar args
  lbl=$1; shift
  d=/tmp/dm_$lbl; rm -rf "$d"; mkdir -p "$d"
  st=$(IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./tvar "$@" --dump 2>/dev/null | grep -E "TEX ok|TEX_FAIL|SUBMIT")
  if echo "$st" | grep -q "TEX ok"; then
    t=$(python3 descauto.py "$d" --tlen 0x18 2>/dev/null | grep -A1 TEXDESC | grep '+0000')
    w0=$(echo "$t" | awk '{print $2}'); w1=$(echo "$t" | awk '{print $3}')
    w2=$(echo "$t" | awk '{print $4}'); w3=$(echo "$t" | awk '{print $5}')
    printf 'DIM %-24s w0=%s w1=%s w2=%s w3=%s\n' "$lbl" "$w0" "$w1" "$w2" "$w3" >> "$OUT"
  else
    printf 'DIM %-24s FAIL %s\n' "$lbl" "$(echo $st|head -c60)" >> "$OUT"
  fi
  rm -rf "$d"
}

# --- 2DArray: 14-bit width/height at 16384 + large arrayLength ---
cap arr_16384x4_a2   --type 2darray --w 16384 --h 4     --arraylen 2
cap arr_4x16384_a2   --type 2darray --w 4     --h 16384 --arraylen 2
cap arr_8x8_a2048    --type 2darray --w 8     --h 8     --arraylen 2048
cap arr_8x8_a64      --type 2darray --w 8     --h 8     --arraylen 64
cap arr_5000x5000_a2 --type 2darray --w 5000  --h 5000  --arraylen 2
# --- 3D: depth field at 2048 + asymmetric ---
cap d3d_2048x2x2     --type 3d --w 2048 --h 2 --d 2
cap d3d_2x2x2048     --type 3d --w 2    --h 2 --d 2048
cap d3d_256x256x64   --type 3d --w 256  --h 256 --d 64
# --- Cube: 14-bit square (Private to avoid OOM) ---
cap cube_1024        --type cube --w 1024 --h 1024
cap cube_8192        --type cube --w 8192 --h 8192
echo "wrote $OUT"; cat "$OUT"
