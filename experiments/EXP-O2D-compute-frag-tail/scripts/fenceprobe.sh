#!/bin/bash
# Comprehensive atomic_thread_fence probe: vary flags x order x scope, extract the
# 0x07 fence bytes for each legal combination. Flags need mem_flags:: qualification.
set -u
cd "$(dirname "$0")"
OUT=raw/fenceprobe.txt
mkdir -p raw tmp
echo "# fence flags x order x scope probe ($(date))" > $OUT

gen() { # $1=fence-call-body (uses g/o/i/n)
  cat > tmp/fp.metal <<EOF
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* g [[buffer(0)]], device uint* o [[buffer(2)]],
              uint i [[thread_position_in_grid]], uint n [[threads_per_grid]]) {
    g[i] = i;
    $1;
    o[i] = g[(i + 1) % n];
}
EOF
}
run() { # $1=label $2=call
  gen "$2"
  if ./shdump -o tmp/fp.bin -f k tmp/fp.metal 2>tmp/fp.err; then
    hex=$(python3 agxparse.py tmp/fp.bin --stage compute --extract-hex --symbol _agc.main 2>/dev/null)
    echo "$1 OK $hex" | tee -a $OUT
  else
    echo "$1 FAIL: $(grep -m1 -i error tmp/fp.err | head -c 100)" | tee -a $OUT
  fi
}

echo "## flags (order=seq_cst, default scope)" >> $OUT
for fl in mem_none mem_device mem_threadgroup mem_texture "mem_device|mem_threadgroup"; do
  run "FLAG[$fl]" "atomic_thread_fence(mem_flags::$fl, memory_order_seq_cst)"
done
echo "## orders (flags=mem_device, default scope)" >> $OUT
for od in memory_order_relaxed memory_order_acquire memory_order_release memory_order_acq_rel memory_order_seq_cst; do
  run "ORDER[$od]" "atomic_thread_fence(mem_flags::mem_device, $od)"
done
echo "## scopes (flags=mem_device, order=seq_cst)" >> $OUT
for sc in thread_scope_thread thread_scope_simdgroup thread_scope_threadgroup thread_scope_device; do
  run "SCOPE[$sc]" "atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, $sc)"
done
echo "## threadgroup fence with tg scope (reference to EXP-0025 barrier)" >> $OUT
run "TG_scope_tg" "atomic_thread_fence(mem_flags::mem_threadgroup, memory_order_seq_cst, thread_scope_threadgroup)"
echo "=== DONE ==="
