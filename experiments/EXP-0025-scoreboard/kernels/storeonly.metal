#include <metal_stdlib>
using namespace metal;
kernel void k(device float *out [[buffer(0)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = 1.0f;
}
