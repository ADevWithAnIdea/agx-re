#include <metal_stdlib>
using namespace metal;

// EXP-0096 tg_addr_compute (0x1c) probe kernel. Reproduces, on the LOCAL M4,
// the exact shape that first triggered tg_addr_compute emission (prior A18-side
// evidence, db.json mnemonic "tg_addr_compute", provenance cites own-MSL
// k_thr.metal / EXP-M4-14): a threadgroup float tile populated one element per
// thread from a device input, a barrier, then TWO threadgroup reads at
// compile-time-CONSTANT offsets (+1, +2) from the thread's own threadgroup
// index, masked to the tile size. This experiment discovered (own-shader,
// compile-only, authoring stage) that replacing either constant offset with a
// value loaded from device/idxbuf memory makes tg_addr_compute NOT be emitted
// (see PRE_REGISTRATION.md "authoring-stage negative result") -- so the
// SPLICE variable here is the INSTRUCTION BYTES of tg_addr_compute itself
// (mutated by the harness after compilation), not a kernel source parameter.
// Runtime variation comes from `a[i]` (per-thread device input) and the
// thread's own position, giving a full per-thread output array (256 values)
// whose baseline shape (a[i]=i identity fill) is o[i] = ((i+1)&255) +
// ((i+2)&255) for i in 0..253, with a decodable wraparound at i in {254,255}.
kernel void k(device float* o        [[buffer(0)]],
              const device float* a  [[buffer(1)]],
              uint i  [[thread_position_in_grid]],
              uint li [[thread_position_in_threadgroup]]) {
    threadgroup float tile[256];
    tile[li] = a[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = tile[(li + 1u) & 255u] + tile[(li + 2u) & 255u];
}
