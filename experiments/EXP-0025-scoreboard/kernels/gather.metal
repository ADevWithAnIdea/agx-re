#include <metal_stdlib>
using namespace metal;
kernel void k(device const float *a   [[buffer(0)]],
              device const uint  *idx [[buffer(1)]],
              device float *out        [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[ idx[gid] ];
}
