#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(2)]],
              threadgroup float* tg [[threadgroup(0)]],
              uint i  [[thread_position_in_grid]],
              uint li [[thread_position_in_threadgroup]],
              uint tgsz [[threads_per_threadgroup]]) {
    tg[li] = a[i] * 2.0f;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint j = (li + 1u) % tgsz;
    o[i] = tg[li] + tg[j];
}
