#include <metal_stdlib>
using namespace metal;
// packed_float3 / packed_int4: unaligned tightly-packed vector memory access.
kernel void k(device packed_float3* out [[buffer(0)]],
              device const packed_float3* in [[buffer(1)]],
              device packed_int4* out4 [[buffer(2)]],
              device const packed_int4* in4 [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    packed_float3 v = in[i];
    out[i] = packed_float3(v[2], v[0], v[1]);
    packed_int4 w = in4[i];
    out4[i] = packed_int4(w[3], w[2], w[1], w[0]);
}
