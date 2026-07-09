#include <metal_stdlib>
using namespace metal;
kernel void k_cf_if(device uint* out [[buffer(0)]],
                    device const uint* in [[buffer(1)]],
                    uint tid [[thread_position_in_grid]]) {
    uint x = in[tid];
    if (x > 5u) { out[tid] = x + 1u; }
}
