#include <metal_stdlib>
using namespace metal;
kernel void k(device float2* out [[buffer(0)]],
              device const uint* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = unpack_unorm2x16_to_float(in[tid]);
}
