#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              uint i[[thread_position_in_grid]], uint li[[thread_position_in_threadgroup]]) {
    threadgroup float tile[256];
    tile[li] = a[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = tile[(li+1)&255] + tile[(li+2)&255];
}
