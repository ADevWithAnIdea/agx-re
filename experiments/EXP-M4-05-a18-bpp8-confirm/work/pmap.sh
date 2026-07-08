#!/bin/sh
cd ~/cleanroom_work/exp_bpp8
for cfg in "b8_160 rg32uint 160 160" "b8_320 rg32uint 320 320" "b8_448 rg32uint 448 448"; do
  set -- $cfg; tag=$1; fmt=$2; W=$3; H=$4
  echo "########## $tag ($fmt ${W}x${H}) ##########"
  python3 probe_map.py "maps_$tag" --fmt "$fmt" --w "$W" --h "$H" 2>&1
  echo
done
