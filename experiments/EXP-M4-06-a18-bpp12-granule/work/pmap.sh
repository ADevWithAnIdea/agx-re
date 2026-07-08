#!/bin/sh
# model-INDEPENDENT tile-stride cross-check (r16 / bpp2 only; r8's 8-bit pattern
# is not first-occurrence-invertible). Confirms cols without assuming a cols rule.
cd ~/cleanroom_work/exp_bpp12
for cfg in "b2_192 192 192" "b2_256 256 256" "b2_320 320 320" "b2_448 448 448" "b2_320x192 320 192"; do
  set -- $cfg; tag=$1; W=$2; H=$3
  echo "########## $tag (r16uint ${W}x${H}) ##########"
  python3 stride.py "maps_$tag" --w "$W" --h "$H" --t 64 2>&1
  echo
done
