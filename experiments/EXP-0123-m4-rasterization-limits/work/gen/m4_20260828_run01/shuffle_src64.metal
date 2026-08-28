#include <metal_stdlib>
using namespace metal;
kernel void cs_shuf(device uint* out [[buffer(0)]], uint tid [[thread_position_in_grid]], uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane * 10 + 1;
    uint got = simd_shuffle(v, (uint)64);
    out[tid] = got;
}
