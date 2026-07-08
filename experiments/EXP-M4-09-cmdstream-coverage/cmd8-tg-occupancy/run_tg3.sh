#!/bin/sh
# run_tg3.sh — Sub-task (1) fine map + shader-dependence + grid-dependence.
# (a) Fine 1-D add3 map, numGroups=8 fixed, req=1..40, 60..70, 96..104, 126..136, 190..210.
# (b) Shader-dependence: add3 vs tgmem(barrier+shared) vs heavy(high-GPR) at same req.
# (c) Grid-dependence for small req: numGroups 1/2/4/8/16 at req=3 and req=7.
# CLEAN-ROOM: OWN-SHADER + DATA-TRACE.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x800
OUT=caps_tg3
rm -rf "$OUT"; mkdir -p "$OUT"

eff(){ f=$(ls "$1"/bo_*va100000b0000_*.hex 2>/dev/null|head -1); [ -n "$f" ] && python3 cdmread.py "$f" 2>/dev/null|head -1|sed -n 's/.*tg=(\([0-9,]*\)).*/\1/p'; }
# runG kernel numGroups reqtg
runG(){
  kern="$1"; ng="$2"; t="$3"; label="${kern}_ng${ng}_t${t}"
  d="$OUT/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar --kernel "$kern" --groups \
      --gx "$ng" --tgx "$t" --dump > "$OUT/$label.out" 2>&1 || true
  printf "%-22s req=%-5s eff_tg=%s\n" "$label" "$t" "$(eff "$d")"
}

echo "===== (a) fine 1-D add3, numGroups=8 ====="
for t in $(seq 1 40) 44 48 52 56 60 61 62 63 64 65 66 67 68 70 72 80 88 96 97 98 99 100 101 102 103 104 120 126 127 128 129 130 131 132 134 136 144 160 176 192 200 208 224 256; do
  runG add3 8 "$t"
done

echo "===== (b) shader-dependence: add3 vs tgmem vs heavy, numGroups=4 ====="
for t in 3 7 16 33 40 48 65 80 100 128 130 200; do
  runG add3  4 "$t"
  runG tgmem 4 "$t"
  runG heavy 4 "$t"
done

echo "===== (c) grid-dependence small req (numGroups 1/2/4/8/16/32) ====="
for ng in 1 2 4 8 16 32; do runG add3 "$ng" 3; done
for ng in 1 2 4 8 16 32; do runG add3 "$ng" 7; done
for ng in 1 2 4 8 16 32; do runG add3 "$ng" 5; done
echo DONE_TG3
