#!/bin/sh
cd ~/cleanroom_work/exp_bpp8
mkdir -p raw
# consolidated tvcheck (twiddle-solve) across all configs
{
for cfg in "b8_96 rg32uint 96 96" "b8_160 rg32uint 160 160" "b8_288 rg32uint 288 288" \
           "b8_320 rg32uint 320 320" "b8_448 rg32uint 448 448" "b8_160x256 rg32uint 160 256" \
           "b4_160 r32uint 160 160" "b16_96 rgba32uint 96 96" "b16_160 rgba32uint 160 160"; do
  set -- $cfg; tag=$1; fmt=$2; W=$3; H=$4
  echo "########## $tag ($fmt ${W}x${H}) ##########"
  python3 tvcheck.py "maps_$tag" --fmt "$fmt" --w "$W" --h "$H" 2>&1
  echo
done
} > raw/tvcheck_all.txt

# consolidated probe_map (model-independent stride inverter) across all bpp8 configs
{
for cfg in "b8_96 rg32uint 96 96" "b8_160 rg32uint 160 160" "b8_288 rg32uint 288 288" \
           "b8_320 rg32uint 320 320" "b8_448 rg32uint 448 448" "b8_160x256 rg32uint 160 256" \
           "b4_160 r32uint 160 160" "b16_96 rgba32uint 96 96" "b16_160 rgba32uint 160 160"; do
  set -- $cfg; tag=$1; fmt=$2; W=$3; H=$4
  echo "########## $tag ($fmt ${W}x${H}) ##########"
  python3 probe_map.py "maps_$tag" --fmt "$fmt" --w "$W" --h "$H" 2>&1
  echo
done
} > raw/probe_map_all.txt

# copy the texture BACKING BO snapshot (va 0x10000080000) for each config as evidence
mkdir -p raw/backing
for tag in b8_96 b8_160 b8_288 b8_320 b8_448 b8_160x256 b4_160 b16_96 b16_160; do
  f=$(ls maps_$tag/*va10000080000* 2>/dev/null | head -1)
  if [ -n "$f" ]; then cp "$f" "raw/backing/${tag}_backing.hex"; fi
done
# also copy the descriptor via descauto for each (base VA + layout flags evidence)
{
for cfg in "b8_96 96 96" "b8_160 160 160" "b8_288 288 288" "b8_320 320 320" "b8_448 448 448" \
           "b8_160x256 160 256" "b4_160 160 160" "b16_96 96 96" "b16_160 160 160"; do
  set -- $cfg; tag=$1
  echo "########## $tag ##########"
  python3 descauto.py "maps_$tag" 2>&1
  echo
done
} > raw/descriptors_all.txt

echo "=== raw/ contents ==="
ls -la raw raw/backing
echo "=== backing hex sizes (lines) ==="
wc -l raw/backing/*.hex
