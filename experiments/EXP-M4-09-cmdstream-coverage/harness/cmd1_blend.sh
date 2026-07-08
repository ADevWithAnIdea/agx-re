#!/bin/sh
# CMD-1 — Blend STATE-POOL (0x58000) decode across all 19 factors x 5 ops (per-RGB and
# per-alpha) + dual-source + write-mask + enable. CLEAN-ROOM: we decode the traceable
# 0x58000 state bytes only. We also byte-COUNT how many words change in the FS code BO
# (0x10000000000) purely to CLASSIFY "state-only vs FS-rewrite" — we never interpret /
# disassemble those code bytes. Runs on the LOCAL M4.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib
BIG=0x9000   # enough to reach 0x58000 pool + a slice of the code BO for the change-count
rm -rf b_caps b_an; mkdir -p b_caps b_an

cap() {  # cap LABEL -- <svar args>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="b_caps/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$BIG IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./svar "$@" --dump > "$d.out" 2>&1 || true
  grep -qE 'status=4' "$d.out" && echo "  [$label] ok" || echo "  [$label] FAIL: $(grep -iE 'fail|error|status|ARGERR' $d.out|head -1)"
}

echo "=== baselines ==="
cap noblend   --                 # blend disabled
cap bl_ref    --blend            # blend enabled, default srcalpha/1-srcalpha add

echo "=== write-mask sweep (blend on) ==="
for m in 0 1 2 4 8 3 5 10 12 15; do cap wmask_$m -- --blend --wmask $m; done
echo "=== write-mask sweep (blend OFF) ==="
for m in 0 1 2 4 8 15; do cap nwmask_$m -- --wmask $m; done

FACS="zero one srccolor 1-srccolor srcalpha 1-srcalpha dstcolor 1-dstcolor dstalpha 1-dstalpha srcalphasat blendcolor 1-blendcolor blendalpha 1-blendalpha"
echo "=== srcRGB factor sweep (all 15 non-dual) ==="
for f in $FACS; do cap srgb_$f -- --blend --srgb $f; done
echo "=== dstRGB factor sweep ==="
for f in $FACS; do cap drgb_$f -- --blend --drgb $f; done
echo "=== srcAlpha factor sweep ==="
for f in $FACS; do cap sa_$f -- --blend --salpha $f; done
echo "=== dstAlpha factor sweep ==="
for f in $FACS; do cap da_$f -- --blend --dalpha $f; done

echo "=== op sweep (RGB and alpha) ==="
for op in add sub revsub min max; do cap brgb_$op -- --blend --brgbop $op; done
for op in add sub revsub min max; do cap balpha_$op -- --blend --balphaop $op; done

echo "=== dual-source ==="
cap dref -- --dualsrc
for f in src1color 1-src1color src1alpha 1-src1alpha; do cap dual_$f -- --dualsrc --srgb $f; done

echo "=== DIFFS: 0x58000 state pool (bl_ref reference) ==="
# helper: diff only the 0x58000 pool, print just the +off lines
d58() { python3 bodiff.py "b_caps/$1" "b_caps/$2" --va 0x58000 --maxlen 0x100 2>&1 | grep -E '^\s+\+' ; }
# helper: COUNT how many words differ in the FS code BO (classification only, no interpretation)
codecount() { python3 bodiff.py "b_caps/$1" "b_caps/$2" --va 0x10000000000 --maxlen 0x8000 2>&1 | grep -cE '^\s+\+' ; }

{
echo "### enable: noblend vs bl_ref (0x58000)"; d58 noblend bl_ref; echo
echo "### write-mask (blend on): bl_ref vs wmask_M"
for m in 0 1 2 4 8 3 5 10 12 15; do printf "wmask=%s: " $m; d58 bl_ref wmask_$m | tr '\n' ' '; echo; done
echo
echo "### write-mask (blend OFF): noblend vs nwmask_M"
for m in 0 1 2 4 8 15; do printf "nwmask=%s: " $m; d58 noblend nwmask_$m | tr '\n' ' '; echo; done
} > b_an/writemask_enable.txt 2>&1

for FIELD in srgb drgb sa da; do
{
echo "### $FIELD factor sweep: bl_ref vs each (0x58000 delta | FS-code-word-change-count)"
for f in $FACS; do
  lbl="${FIELD}_$f"
  s=$(d58 bl_ref "$lbl" | tr '\n' ' ')
  c=$(codecount bl_ref "$lbl")
  printf "%-14s | 58000: %-60s | code_words_changed=%s\n" "$f" "${s:-(none)}" "$c"
done
} > b_an/factor_$FIELD.txt 2>&1
done

{
echo "### op sweep (0x58000 delta | FS code-word change count) vs bl_ref"
for op in add sub revsub min max; do
  s=$(d58 bl_ref brgb_$op | tr '\n' ' '); c=$(codecount bl_ref brgb_$op)
  printf "rgbop=%-7s | 58000: %-40s | code_words_changed=%s\n" "$op" "${s:-(none)}" "$c"
done
for op in add sub revsub min max; do
  s=$(d58 bl_ref balpha_$op | tr '\n' ' '); c=$(codecount bl_ref balpha_$op)
  printf "alphaop=%-7s | 58000: %-40s | code_words_changed=%s\n" "$op" "${s:-(none)}" "$c"
done
} > b_an/ops.txt 2>&1

{
echo "### dual-source: bl_ref vs dref, and dref vs dual_* (0x58000 | code change count)"
s=$(d58 bl_ref dref | tr '\n' ' '); c=$(codecount bl_ref dref)
printf "dref(default)  | 58000: %-50s | code_words_changed=%s\n" "${s:-(none)}" "$c"
for f in src1color 1-src1color src1alpha 1-src1alpha; do
  s=$(d58 dref dual_$f | tr '\n' ' '); c=$(codecount dref dual_$f)
  printf "%-14s | 58000: %-50s | code_words_changed=%s\n" "$f" "${s:-(none)}" "$c"
done
} > b_an/dualsrc.txt 2>&1

echo "=== raw 0x58000 first 0xc0 bytes for reference configs ==="
raw58() { f=$(ls b_caps/$1/*va58000_*.hex 2>/dev/null|head -1); [ -n "$f" ] && { echo "## $1"; sed -n '2,14p' "$f"; }; }
{ raw58 noblend; raw58 bl_ref; raw58 wmask_0; raw58 srgb_blendcolor; raw58 srgb_srcalphasat; raw58 dref; } > b_an/raw58.txt 2>&1

echo "=== DONE. analysis files in b_an/ ==="
ls b_an/
