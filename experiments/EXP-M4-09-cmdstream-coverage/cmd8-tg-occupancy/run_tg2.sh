#!/bin/sh
# run_tg2.sh — Sub-task (1) REDO: multi-threadgroup tg rounding.
# The first sweep used grid==tg (a single threadgroup) which always records tg
# VERBATIM. Real rounding only appears with MULTIPLE threadgroups. Two modes:
#   A) dispatchThreadgroups (--groups): gx=numGroups, tgx=local size. The clean
#      "what threadgroup size does the driver program for a requested local size".
#   B) dispatchThreads: grid=total threads, tg=requested; Metal's non-uniform path.
# Discriminating values chosen so next-pow2 != next-mult-of-32:
#   65,80,96 -> m32=96 vs pow2=128 ;  130,160,192,200,224 -> m32 vs pow2=256.
# CLEAN-ROOM: OWN-SHADER (add3) + DATA-TRACE.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x800
OUT=caps_tg2
rm -rf "$OUT"; mkdir -p "$OUT"

# runG LABEL  numgx numgy numgz  tgx tgy tgz   (dispatchThreadGROUPS)
runG(){
  label="$1"; ngx="$2"; ngy="$3"; ngz="$4"; tx="$5"; ty="$6"; tz="$7"
  d="$OUT/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar --kernel add3 --groups \
      --gx "$ngx" --gy "$ngy" --gz "$ngz" --tgx "$tx" --tgy "$ty" --tgz "$tz" \
      --dump > "$OUT/$label.out" 2>&1 || true
  f=$(ls "$d"/bo_*va100000b0000_*.hex 2>/dev/null | head -1)
  rec=""; [ -n "$f" ] && rec=$(python3 cdmread.py "$f" 2>/dev/null | head -1 | sed 's/.*grid/grid/')
  printf "%-16s GROUPS n=(%s,%s,%s) req_tg=(%s,%s,%s) | %s\n" "$label" "$ngx" "$ngy" "$ngz" "$tx" "$ty" "$tz" "$rec"
}
# runT LABEL gridx gridy gridz tgx tgy tgz   (dispatchThreads, multi-group)
runT(){
  label="$1"; gx="$2"; gy="$3"; gz="$4"; tx="$5"; ty="$6"; tz="$7"
  d="$OUT/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar --kernel add3 \
      --gx "$gx" --gy "$gy" --gz "$gz" --tgx "$tx" --tgy "$ty" --tgz "$tz" \
      --dump > "$OUT/$label.out" 2>&1 || true
  f=$(ls "$d"/bo_*va100000b0000_*.hex 2>/dev/null | head -1)
  rec=""; [ -n "$f" ] && rec=$(python3 cdmread.py "$f" 2>/dev/null | head -1 | sed 's/.*grid/grid/')
  printf "%-16s THREADS grid=(%s,%s,%s) req_tg=(%s,%s,%s) | %s\n" "$label" "$gx" "$gy" "$gz" "$tx" "$ty" "$tz" "$rec"
}

echo "===== A) dispatchThreadgroups, numGroups=4, 1-D tg sweep ====="
for t in 1 2 3 7 16 17 31 32 33 40 48 63 64 65 80 96 100 127 128 130 160 192 200 224 256 512 1024; do
  runG "G1_$t" 4 1 1 "$t" 1 1
done

echo "===== A2) dispatchThreadgroups, numGroups=4, 2-D tg sweep ====="
runG G2_3x5   4 4 1 3 5 1
runG G2_5x3   4 4 1 5 3 1
runG G2_7x7   4 4 1 7 7 1
runG G2_8x8   4 4 1 8 8 1
runG G2_16x16 4 4 1 16 16 1
runG G2_10x10 4 4 1 10 10 1
runG G2_6x6   4 4 1 6 6 1
runG G2_1x32  4 4 1 1 32 1
runG G2_32x1  4 4 1 32 1 1
runG G2_4x17  4 4 1 4 17 1
runG G2_3x40  4 4 1 3 40 1
runG G2_40x3  4 4 1 40 3 1
runG G2_5x65  4 4 1 5 65 1

echo "===== A3) dispatchThreadgroups, numGroups=2, 3-D tg sweep ====="
runG G3_4x4x4 2 2 2 4 4 4
runG G3_2x3x5 2 2 2 2 3 5
runG G3_8x8x8 2 2 2 8 8 8
runG G3_3x5x7 2 2 2 3 5 7

echo "===== B) dispatchThreads multi-group (grid = 8*tg, exact multiple) ====="
for t in 1 3 7 16 17 31 32 33 48 64 65 96 100 128 130 160 200 224 256; do
  runT "T1_$t" $((t*8)) 1 1 "$t" 1 1
done
echo "===== B2) dispatchThreads 2-D multi-group ====="
runT T2_3x5   24 40 1 3 5 1
runT T2_7x7   56 56 1 7 7 1
runT T2_10x10 80 80 1 10 10 1
runT T2_5x65  40 520 1 5 65 1

echo DONE_TG2
