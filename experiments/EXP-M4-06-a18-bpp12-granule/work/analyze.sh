#!/bin/sh
# tvcheck twiddle-solve for every config (full-grid mismatch per cols-rule + BO size).
cd ~/cleanroom_work/exp_bpp12
for cfg in "b1_64 r8uint 64 64" "b1_128 r8uint 128 128" "b1_192 r8uint 192 192" \
           "b1_256 r8uint 256 256" "b1_320 r8uint 320 320" "b1_192x320 r8uint 192 320" \
           "b2_192 r16uint 192 192" "b2_256 r16uint 256 256" "b2_320 r16uint 320 320" \
           "b2_448 r16uint 448 448" "b2_320x192 r16uint 320 192"; do
  set -- $cfg; tag=$1; fmt=$2; W=$3; H=$4
  echo "########## $tag ($fmt ${W}x${H}) ##########"
  python3 tvcheck.py "maps_$tag" --fmt "$fmt" --w "$W" --h "$H" 2>&1
  echo
done
