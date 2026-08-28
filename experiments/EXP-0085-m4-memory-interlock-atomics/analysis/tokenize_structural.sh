#!/bin/sh
# EXP-0085 structural (tokenization) re-validation, M4.
#
# Read-only use of tools/shdump (compile OUR MSL, extract OUR compiled AGX
# bytes) and tools/agx-isa (disassemble OUR bytes). Clean-room: OWN-SHADER.
# Neither tool is modified; both are invoked exactly as documented in their
# own READMEs. Output is appended (never overwritten) to
# analysis/tokenize_evidence.txt as the structural record backing the
# MEM-13/MEM-14 interlock re-validation and the ATOM-05/06 SIMD-pre-combine
# boundary finding (see RESULTS.md).
#
# Usage: sh analysis/tokenize_structural.sh   (run from the experiment root)
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
W="$HERE/work"
OUT="$HERE/analysis/tokenize_evidence.txt"
mkdir -p "$W"

if [ ! -x "$W/shdump" ]; then
  xcrun clang -fobjc-arc -framework Metal -framework Foundation \
    -o "$W/shdump" "$REPO/tools/shdump/shdump.m"
fi

: > "$OUT"
echo "# EXP-0085 structural tokenization evidence (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))" >> "$OUT"
echo "# tool: tools/shdump (read-only) + tools/agx-isa/agxisa.py (read-only), our own compiled kernel bytes only" >> "$OUT"

emit() {
  src="$1"; fn="$2"
  "$W/shdump" -o "$W/$fn.bin" -f "$fn" "$HERE/kernels/$src" 2>"$W/$fn.shdump.log" || true
  echo "" >> "$OUT"
  echo "=== $fn  (source: kernels/$src) ===" >> "$OUT"
  HEX=$(python3 "$REPO/tools/shdump/agxparse.py" "$W/$fn.bin" --extract-hex 2>>"$W/$fn.shdump.log") || true
  if [ -z "$HEX" ]; then
    echo "(extract failed; see $fn.shdump.log)" >> "$OUT"
  else
    python3 "$REPO/tools/agx-isa/agxisa.py" tokenize "$HEX" >> "$OUT" 2>&1
  fi
}

for fn in il_load_alu il_gather il_atomic_alu il_store_src il_atomic_src; do
  emit interlock.metal "$fn"
done
for fn in da_add da_exch da_exch_noret da_store; do
  emit atomics.metal "$fn"
done
for fn in da_add_static0 da_xor_static0 da_umin_static0 da_exch_static0 da_cmpxchg_static0; do
  emit atomics.metal "$fn"
done

echo "" >> "$OUT"
echo "wrote $(wc -l < "$OUT") lines to $OUT"
