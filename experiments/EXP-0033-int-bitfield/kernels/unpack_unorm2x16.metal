#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *a [[buffer(0)]],
              device float2 *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = unpack_unorm2x16_to_float(a[gid]);
}
