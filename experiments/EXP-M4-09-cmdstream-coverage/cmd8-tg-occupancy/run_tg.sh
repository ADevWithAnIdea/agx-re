#!/bin/sh
# run_tg.sh — Sub-task (1): threadgroup rounding sweep.
# For each requested threadsPerThreadgroup (tgx,tgy,tgz), dispatchThreads with
# grid == tg (exactly one threadgroup, always valid), capture the CDM record,
# and read the driver-chosen EFFECTIVE tg at +0x1c/+0x20/+0x24.
# CLEAN-ROOM: OWN-SHADER (add3 = our MSL) + DATA-TRACE (our own cmdbuf bytes).
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x800
OUT=caps_tg
rm -rf "$OUT"; mkdir -p "$OUT"

# run LABEL  tgx tgy tgz   [gridx gridy gridz]  — grid defaults to tg (one group)
run(){
  label="$1"; tx="$2"; ty="$3"; tz="$4"
  gx="${5:-$tx}"; gy="${6:-$ty}"; gz="${7:-$tz}"
  d="$OUT/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar --kernel add3 \
      --gx "$gx" --gy "$gy" --gz "$gz" --tgx "$tx" --tgy "$ty" --tgz "$tz" \
      --dump > "$OUT/$label.out" 2>&1 || true
  f=$(ls "$d"/bo_*va100000b0000_*.hex 2>/dev/null | head -1)
  rec=""
  [ -n "$f" ] && rec=$(python3 cdmread.py "$f" 2>/dev/null | head -1)
  printf "%-16s req_tg=(%s,%s,%s) grid=(%s,%s,%s) | %s\n" "$label" "$tx" "$ty" "$tz" "$gx" "$gy" "$gz" "$rec"
}

echo "===== 1-D sweep (tgy=tgz=1) ====="
for t in 1 2 3 7 16 17 31 32 33 48 64 65 96 100 128 200 256 512 1024; do
  run "d1_$t" "$t" 1 1
done

echo "===== 2-D sweep (tgz=1) ====="
run d2_3x5   3 5 1
run d2_5x3   5 3 1
run d2_7x7   7 7 1
run d2_8x8   8 8 1
run d2_16x16 16 16 1
run d2_10x10 10 10 1
run d2_3x3   3 3 1
run d2_6x6   6 6 1
run d2_1x32  1 32 1
run d2_32x1  32 1 1
run d2_4x17  4 17 1

echo "===== 3-D sweep ====="
run d3_4x4x4 4 4 4
run d3_2x3x5 2 3 5
run d3_8x8x8 8 8 8

echo "===== grid-independence controls (same tg, bigger grid) ====="
# tg=(32,1,1) with grids 32 / 256 / 1024 — effective tg should NOT change with grid
run ctl_g32_gr32   32 1 1   32 1 1
run ctl_g32_gr256  32 1 1  256 1 1
run ctl_g32_gr1024 32 1 1 1024 1 1
# tg=(100) with grid 100 vs 1000
run ctl_t100_gr100  100 1 1  100 1 1
run ctl_t100_gr1000 100 1 1 1000 1 1

echo DONE_TG
