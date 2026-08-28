#include <metal_stdlib>
using namespace metal;
kernel void cs_shuf(device uint* out [[buffer(0)]], uint tid [[thread_position_in_grid]], uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane; // value = own lane id
    uint got32 = simd_shuffle(v, 32);   // out-of-range source lane (simdgroup width 32, valid 0..31)
    uint got33 = simd_shuffle(v, 33);
    uint got0  = simd_shuffle(v, 0);
    out[tid*3+0] = got32; out[tid*3+1] = got33; out[tid*3+2] = got0;
}
