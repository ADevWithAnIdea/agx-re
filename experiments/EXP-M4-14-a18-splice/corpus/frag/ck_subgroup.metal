#include <metal_stdlib>
using namespace metal;

// Provoke the byte0-low-nibble-4 datapath-read op (R9: simd reductions / SFU /
// intersection getters). Several subgroup/SFU ops to maximize the chance the
// compiler emits the residual 0x04-group op.
kernel void k(device float *out [[buffer(0)]],
              device const float *in [[buffer(1)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    float v = in[tid];
    float p = simd_product(v);              // subgroup multiply reduction
    float s = simd_prefix_exclusive_sum(v); // subgroup scan
    float b = simd_broadcast_first(v);      // subgroup broadcast
    float t = precise::cos(v * 3.14159265f);// SFU transcendental
    out[tid] = p + s + b + t + float(lane);
}
