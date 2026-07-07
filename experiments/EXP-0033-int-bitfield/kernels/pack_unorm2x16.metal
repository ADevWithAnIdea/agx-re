#include <metal_stdlib>
using namespace metal;

kernel void k(device const float2 *a [[buffer(0)]],
              device uint *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = pack_float_to_unorm2x16(a[gid]);
}
