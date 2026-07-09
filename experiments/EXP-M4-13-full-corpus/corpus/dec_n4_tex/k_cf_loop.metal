#include <metal_stdlib>
using namespace metal;
kernel void k_cf_loop(device uint* out [[buffer(0)]],
                      device const uint* in [[buffer(1)]],
                      uint tid [[thread_position_in_grid]]) {
    uint s = 0;
    for (uint i = 0; i < in[tid]; ++i) s += i;
    out[tid] = s;
}
