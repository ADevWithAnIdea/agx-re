#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint gid [[thread_position_in_grid]],
              uint v [[threads_per_threadgroup]]) {
    out[gid] = v;
}
