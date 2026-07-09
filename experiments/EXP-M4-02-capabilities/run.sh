#!/bin/bash
# EXP-M4-02 run.sh — build + run the M4 capability probes locally.
# Clean-room: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
set -e
cd "$(dirname "$0")"
mkdir -p raw

echo "[1/4] build metal_caps"
clang -fobjc-arc -O0 -framework Metal -framework Foundation metal_caps.m -o raw/metal_caps

echo "[2/4] build msl_probes"
clang -fobjc-arc -O0 -framework Metal -framework Foundation msl_probes.m -o raw/msl_probes

echo "[3/4] run device-capability probe"
./raw/metal_caps | tee raw/metal_caps.txt

echo "[4/4] run MSL compile-accept/reject battery"
./raw/msl_probes | tee raw/msl_probes.txt

echo "== GPU config (IORegistry / system_profiler; runtime data values only) =="
{
  echo "--- hw.model / memsize / pagesize ---"
  sysctl hw.model hw.memsize hw.pagesize
  echo "--- AGXAccelerator model + gpu-core-count ---"
  ioreg -rc AGXAccelerator 2>/dev/null | grep -i -E 'gpu-core-count|"model"' | head
  echo "--- system_profiler SPDisplaysDataType ---"
  system_profiler SPDisplaysDataType 2>/dev/null | grep -i -E 'Chipset|Vendor|Cores|Metal|Device ID'
} | tee raw/gpu_config.txt
echo "DONE"
