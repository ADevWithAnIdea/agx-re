#!/bin/sh
# RT-2a Phase C — falsify USC bind grammar (arg buffer 0x10000248000).
# Claims: 2-ptr header [tex-array VA][samp-array VA]; num_tex=(samp-tex)/0x20;
#         num_samp=(term-samp)/8; buffers -> 0x10000100000+0xa0.
# Adversarial: many tex+samp+buf, mismatched counts.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x1000
rm -rf capsC hexC; mkdir -p capsC hexC
ru(){ label="$1"; shift; d="capsC/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG="capsC/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./uvar "$@" --dump > "capsC/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E '^CONFIG' capsC/$label.out|head -1)"; }
ru t1s1     --ftex 1 --fsmp 1
ru t2s2     --ftex 2 --fsmp 2
ru t3s3     --ftex 3 --fsmp 3
ru t8s4b4   --ftex 8 --fsmp 4 --fbuf 4
ru t8s8     --ftex 8 --fsmp 8
ru t3s1     --ftex 3 --fsmp 1
ru t1s3     --ftex 1 --fsmp 3
ru t4s0     --ftex 4 --fsmp 0
ru t0s0b4   --ftex 0 --fsmp 0 --fbuf 4
ru t5s2b3   --ftex 5 --fsmp 2 --fbuf 3
ru t7s3     --ftex 7 --fsmp 3

echo "=== USC arg-buffer header parse (0x10000248000) ==="
P(){ label="$1"; et="$2"; es="$3"
  f=$(ls capsC/$label/*va10000248000_*.hex 2>/dev/null|head -1)
  echo "--- $label (tex=$et samp=$es) ---"
  if [ -n "$f" ]; then python3 uscread.py "$f" "$et" "$es"; else echo "  NO ARGBUF 0x10000248000"; fi
}
P t1s1 1 1
P t2s2 2 2
P t3s3 3 3
P t8s4b4 8 4
P t8s8 8 8
P t3s1 3 1
P t1s3 1 3
P t4s0 4 0
P t0s0b4 0 0
P t5s2b3 5 2
P t7s3 7 3

echo "=== buffers table 0x10000100000 (+0xa0) — buffer VAs in order ==="
for label in t8s4b4 t5s2b3 t0s0b4; do
  echo "--- $label ---"
  grep -E 'fbuf' capsC/$label.out
  f=$(ls capsC/$label/*va10000100000_*.hex 2>/dev/null|head -1)
  [ -n "$f" ] && sed -n '/^000000a0:/,/^000000e0:/p' "$f"
done

echo "=== curated argbuf hex ==="
kb(){ f=$(ls capsC/$1/*va10000248000_*.hex 2>/dev/null|head -1); [ -n "$f" ] && head -14 "$f" > "hexC/$2.hex" || echo "no argbuf $1"; }
kb t8s4b4 t8s4b4
kb t3s1 t3s1
kb t1s3 t1s3
kb t8s8 t8s8
echo DONE_PHASE_C