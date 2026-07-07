#!/bin/bash
# EXP-0002 probe_hw.sh  —  Clean-room category: HW-PROBE
#
# Queries the target's hardware identity & userspace-interface surface using ONLY
# read-only OS query tools:
#   - ioreg           : reads the live IORegistry / IODeviceTree (a runtime data
#                       structure describing hardware + driver match state)
#   - sysctl          : reads kernel-exported hardware parameters
#   - system_profiler : reads the system configuration report
#   - kextstat/kmutil : list LOADED kext METADATA (bundle id + version only)
#
# It does NOT disassemble, decompile, or introspect the machine code of any binary.
# It does NOT run any GPU work. All output is non-copyrightable hardware/config data.
#
# Run ON the target device (writes to ./raw). Re-runnable by any third party.
set -u
OUT="${1:-raw}"
mkdir -p "$OUT"
cd "$OUT" || exit 1

# --- 1. GPU accelerator node (full properties), rooted at the matching subtree ---
ioreg -rw0 -l -c AGXAcceleratorG17P > ioreg_AGXAcceleratorG17P.txt 2>&1
# trimmed key-properties view (drops the huge IOReportLegend / stats blobs)
grep -v -E "IOReportLegend|PerformanceStatistics|SchedulerState|AGCInfo|IOReportChannel" \
    ioreg_AGXAcceleratorG17P.txt > ioreg_AGXAcceleratorG17P_keyprops.txt
ioreg -rw0 -l -c AGXDeviceUserClient > ioreg_AGXDeviceUserClient.txt 2>&1

# --- 2. Device-tree GPU node (compatible strings, memory regions, perf states) ---
ioreg -lw0 -p IODeviceTree -n sgx -r > ioreg_dt_sgx.txt 2>&1
ioreg -lw0 -p IODeviceTree            > ioreg_devicetree.txt 2>&1

# --- 3. Full live registry -> GPU-relevant node hierarchy + class inventory ---
ioreg -lw0 > /tmp/ioreg_full.$$ 2>&1
grep -n -E "\+-o .*<class" /tmp/ioreg_full.$$ | grep -i -E "gpu|agx|accel|sgx|metal" \
    > ioreg_full_gpu_nodes.txt
grep -o -E "class [A-Za-z0-9_]+" /tmp/ioreg_full.$$ | sort | uniq -c | sort -rn \
    > classes_all_counts.txt
grep -i -E "IOGPU|AGX|IOAccel|IOUserClient|Metal" classes_all_counts.txt > classes_gpu.txt
grep -o -E "\"IOGPU[A-Za-z0-9_]+\"" /tmp/ioreg_full.$$ | sort -u > iogpu_class_names.txt
grep -o -E "\"AGX[A-Za-z0-9_]+\""  /tmp/ioreg_full.$$ | sort -u > agx_class_names.txt
rm -f /tmp/ioreg_full.$$

# --- 4. sysctl hardware / cpu ---
sysctl hw machdep.cpu > sysctl_hw.txt 2>&1

# --- 5. system_profiler (GPU/display) ---
system_profiler SPDisplaysDataType > sysprofiler_displays.txt 2>&1

# --- 6. loaded GPU-related kext metadata (names + versions only) ---
kextstat 2>/dev/null | grep -i -E "gpu|agx|iogpu|accel|metal" > kextstat_gpu.txt
kmutil showloaded 2>/dev/null | grep -i -E "gpu|agx|iogpu|accel|metal" > kmutil_gpu.txt

echo "done -> $OUT"
