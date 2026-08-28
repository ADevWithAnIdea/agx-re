#include <metal_stdlib>
using namespace metal;
// ATOM-09 sharpening: identical to EXP-0025's tgdiv2.metal (threadgroup-memory
// scratch array, per-lane variable LCG delay) but threadgroup_barrier(mem_none)
// instead of mem_threadgroup. The instruction bytes are structurally identical
// in shape to mem_threadgroup (own-compile census, this experiment) -- this
// tests whether mem_none ALSO still provides real threadgroup-memory
// convergence+visibility on this hardware (same instruction, different
// mem_scope tag) or whether omitting the memory-class tag silently drops
// visibility despite still emitting the barrier instruction.
kernel void k(device const uint *a [[buffer(0)]], device uint *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[256];
    uint d = a[gid];
    uint iters = (lid + 1u) * 32u;
    for (uint i = 0u; i < iters; i++) { d = d * 1664525u + 1013904223u; }
    scratch[lid] = d;
    threadgroup_barrier(mem_flags::mem_none);
    out[gid] = scratch[255u - lid];
}
