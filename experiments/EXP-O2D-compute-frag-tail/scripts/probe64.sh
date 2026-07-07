#!/bin/bash
# Isolated probe: which 64-bit atomic ops does MSL expose, and at which language
# version? Each op is a standalone single-function source (so one rejection does
# not mask the others). Also prints the extracted bytes for legal ops.
set -u
cd "$(dirname "$0")"
mkdir -p raw tmp
OUT=raw/probe64.txt
echo "# 64-bit atomic op probe ($(date))" > $OUT

test_op() { # $1=name $2=type(atomic<ulong>) $3=scalar(ulong) $4=call
  cat > tmp/p64.metal <<EOF
#include <metal_stdlib>
using namespace metal;
kernel void k(device $2* a [[buffer(0)]], device const $3* v [[buffer(1)]],
              device $3* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = $4;
}
EOF
  for ver in "" "3.1" "3.2" "4.0"; do
    if MSLVER=$ver ./shdump_v -o tmp/p64.bin -f k tmp/p64.metal 2>tmp/p64.err; then
      hex=$(python3 agxparse.py tmp/p64.bin --stage compute --extract-hex --symbol _agc.main 2>/dev/null)
      echo "$1 ver[${ver:-default}] OK $hex" | tee -a $OUT
      return
    fi
  done
  echo "$1 ALL-VER FAIL: $(grep -m1 -i error tmp/p64.err | head -c 130)" | tee -a $OUT
}

# 64-bit
test_op a64_add   "device atomic<ulong>" ulong "atomic_fetch_add_explicit(a, v[i], memory_order_relaxed)"
test_op a64_umin  "device atomic<ulong>" ulong "atomic_fetch_min_explicit(a, v[i], memory_order_relaxed)"
test_op a64_umax  "device atomic<ulong>" ulong "atomic_fetch_max_explicit(a, v[i], memory_order_relaxed)"
test_op a64_smin  "device atomic<long>"  long  "atomic_fetch_min_explicit(a, v[i], memory_order_relaxed)"
test_op a64_and   "device atomic<ulong>" ulong "atomic_fetch_and_explicit(a, v[i], memory_order_relaxed)"
test_op a64_or    "device atomic<ulong>" ulong "atomic_fetch_or_explicit(a, v[i], memory_order_relaxed)"
test_op a64_xor   "device atomic<ulong>" ulong "atomic_fetch_xor_explicit(a, v[i], memory_order_relaxed)"
test_op a64_xchg  "device atomic<ulong>" ulong "atomic_exchange_explicit(a, v[i], memory_order_relaxed)"
test_op a64_load  "device atomic<ulong>" ulong "atomic_load_explicit(a, memory_order_relaxed)"
# 32-bit reference (for width-field diff)
test_op a32_add   "device atomic<uint>"  uint  "atomic_fetch_add_explicit(a, v[i], memory_order_relaxed)"
test_op a32_umin  "device atomic<uint>"  uint  "atomic_fetch_min_explicit(a, v[i], memory_order_relaxed)"
test_op a32_xchg  "device atomic<uint>"  uint  "atomic_exchange_explicit(a, v[i], memory_order_relaxed)"
echo "=== DONE ==="
