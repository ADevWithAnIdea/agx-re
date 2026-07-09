#include <metal_stdlib>
using namespace metal;
kernel void k_cf_ret(device uint* out [[buffer(0)]],
                     device const uint* in [[buffer(1)]],
                     uint tid [[thread_position_in_grid]]) {
    if (in[tid] == 0u) return;
    out[tid] = 42u;
}
