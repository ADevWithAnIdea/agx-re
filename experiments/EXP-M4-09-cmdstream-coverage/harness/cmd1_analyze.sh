#!/bin/sh
# CMD-1 analysis (captures already in b_caps/). No set -e.
cd "$(dirname "$0")"
rm -rf b_an; mkdir -p b_an
FACS="zero one srccolor 1-srccolor srcalpha 1-srcalpha dstcolor 1-dstcolor dstalpha 1-dstalpha srcalphasat blendcolor 1-blendcolor blendalpha 1-blendalpha"

d58() { python3 bodiff.py "b_caps/$1" "b_caps/$2" --va 0x58000 --maxlen 0x100 2>/dev/null | grep -E '^[[:space:]]+\+' ; }
codecount() { n=$(python3 bodiff.py "b_caps/$1" "b_caps/$2" --va 0x10000000000 --maxlen 0x8000 2>/dev/null | grep -cE '^[[:space:]]+\+'); echo "$n"; }

{
echo "### enable: noblend vs bl_ref (0x58000)"; d58 noblend bl_ref; echo
echo "### write-mask (blend on): bl_ref vs wmask_M   [+0x5c low nibble = mask]"
for m in 0 1 2 4 8 3 5 10 12 15; do printf "wmask=%-3s: " $m; d58 bl_ref wmask_$m | tr '\n' ' '; echo; done
echo
echo "### write-mask (blend OFF): noblend vs nwmask_M"
for m in 0 1 2 4 8 15; do printf "nwmask=%-3s: " $m; d58 noblend nwmask_$m | tr '\n' ' '; echo; done
} > b_an/writemask_enable.txt 2>&1

for FIELD in srgb drgb sa da; do
{
echo "### $FIELD factor sweep: bl_ref(=srcalpha/1-srcalpha add) vs each"
echo "###   58000 delta | FS code-word change count (classification only, no interpretation)"
for f in $FACS; do
  s=$(d58 bl_ref "${FIELD}_$f" | tr '\n' ' ')
  c=$(codecount bl_ref "${FIELD}_$f")
  printf "%-14s | 58000: %-62s | code_words=%s\n" "$f" "${s:-(none)}" "$c"
done
} > b_an/factor_$FIELD.txt 2>&1
done

{
echo "### op sweep vs bl_ref  (58000 delta | FS code-word change count)"
for op in add sub revsub min max; do
  s=$(d58 bl_ref brgb_$op | tr '\n' ' '); c=$(codecount bl_ref brgb_$op)
  printf "rgbop=%-7s | 58000: %-46s | code_words=%s\n" "$op" "${s:-(none)}" "$c"
done
for op in add sub revsub min max; do
  s=$(d58 bl_ref balpha_$op | tr '\n' ' '); c=$(codecount bl_ref balpha_$op)
  printf "alphaop=%-7s | 58000: %-46s | code_words=%s\n" "$op" "${s:-(none)}" "$c"
done
} > b_an/ops.txt 2>&1

{
echo "### dual-source (58000 delta | FS code-word change count)"
s=$(d58 bl_ref dref | tr '\n' ' '); c=$(codecount bl_ref dref)
printf "%-14s | 58000: %-52s | code_words=%s\n" "dref(bl_ref)" "${s:-(none)}" "$c"
for f in src1color 1-src1color src1alpha 1-src1alpha; do
  s=$(d58 dref dual_$f | tr '\n' ' '); c=$(codecount dref dual_$f)
  printf "%-14s | 58000: %-52s | code_words=%s\n" "$f" "${s:-(none)}" "$c"
done
} > b_an/dualsrc.txt 2>&1

# raw 0x58000 first 0xc0 bytes for reference configs
raw58() { f=$(ls b_caps/$1/*va58000_*.hex 2>/dev/null|head -1); if [ -n "$f" ]; then echo "## $1"; sed -n '2,14p' "$f"; echo; fi; }
{ raw58 noblend; raw58 bl_ref; raw58 wmask_0; raw58 srgb_blendcolor; raw58 srgb_srcalphasat; raw58 dref; } > b_an/raw58.txt 2>&1

echo "analysis done:"; ls b_an/
