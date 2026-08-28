#include <metal_stdlib>
using namespace metal;
// ATOM-09/ATOM-10 convergence probe, DEVICE-memory variant of EXP-0025's
// tgdiv2.metal: per-lane variable-length LCG delay (lane 255 runs 8192 iters,
// slowest; lane 0 runs 32 iters, fastest and reads lane 255's slot), but the
// shared array is DEVICE memory (`scratch`, buffer(2)) instead of threadgroup
// memory, and the barrier requests mem_device -- compiles to the device-scope
// barrier form (byte+3=0x85), the exact splice target for ATOM-10 (does
// clearing bit0 -- 0x85->0x84, the same bit distinguishing threadgroup_barrier
// from the standalone mem_fence -- break execution convergence, not just the
// memory-class tag?). scratch is pre-filled with a stale sentinel (0xdeadbeef)
// by the harness so a convergence failure (a lane reading before the slow
// writer finishes) is visible as a wrong/sentinel value, not coincidentally
// correct.
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              device uint *scratch [[buffer(2)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    uint d = a[gid];
    uint iters = (lid + 1u) * 32u;
    for (uint i = 0u; i < iters; i++) { d = d * 1664525u + 1013904223u; }
    scratch[lid] = d;
    threadgroup_barrier(mem_flags::mem_device);
    out[gid] = scratch[255u - lid];
}
