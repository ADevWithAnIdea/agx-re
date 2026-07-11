#!/bin/bash
# EXP-M5-04 reproducibility driver.
# Builds and runs OUR OWN capability probe on the M5 target and pulls raw output back.
# Clean-room: probe.m calls only public Metal APIs on our own program; no Apple binary
# is disassembled. gpu_config.txt is textual ioreg/system_profiler/sysctl DATA only.
#
# Usage: ./run.sh   (from the host; edit HOST if the target IP changes)
set -euo pipefail
HOST=user@192.168.170.253
PW=Password_1
SSH="sshpass -p $PW ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
 -o ConnectTimeout=25 -o PreferredAuthentications=password -o PubkeyAuthentication=no \
 -o IdentitiesOnly=yes -o NumberOfPasswordPrompts=1 $HOST"
DIR=$(cd "$(dirname "$0")" && pwd)
WORK='~/cleanroom_work/EXP-M5-04'

$SSH "mkdir -p $WORK"
cat "$DIR/probe.m" | $SSH "cat > $WORK/probe.m"
$SSH "cd $WORK && clang -fobjc-arc -framework Metal -framework Foundation probe.m -o probe && ./probe" \
  > "$DIR/raw/probe_output.txt"
echo "wrote raw/probe_output.txt"
# GPU config (textual data only)
$SSH 'SDK=$(xcrun --show-sdk-path); \
  echo "--- sw_vers / uname ---"; sw_vers; uname -a; echo; \
  echo "--- hw.model / memsize / pagesize / gpu core count ---"; sysctl hw.model hw.memsize hw.pagesize; echo; \
  echo "--- AGXAccelerator textual props ---"; ioreg -rc AGXAccelerator | grep -iE "\"(model|gpu-core-count|IOClass|device-id|family-name|bundle-id)\""; echo; \
  echo "--- system_profiler SPDisplaysDataType ---"; system_profiler SPDisplaysDataType 2>/dev/null | grep -iE "Chipset|Cores|Vendor|Metal|Device ID"; echo; \
  echo "--- MTLGPUFamily Apple enum from public SDK header ---"; grep -nE "MTLGPUFamilyApple(9|10)|MTLGPUFamilyMetal(3|4)" "$SDK/System/Library/Frameworks/Metal.framework/Headers/MTLDevice.h"; echo; \
  echo "--- MTLSparsePageSize enum from public SDK header ---"; grep -nE "MTLSparsePageSize(16|64|256)" "$SDK/System/Library/Frameworks/Metal.framework/Headers/MTLResource.h"' \
  > "$DIR/raw/gpu_config.txt"
echo "wrote raw/gpu_config.txt"
