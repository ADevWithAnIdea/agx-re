#include <metal_stdlib>
using namespace metal;
kernel void cs_shuf2(device uint* out [[buffer(0)]], constant uint& srcLane [[buffer(1)]],
                      uint tid [[thread_position_in_grid]], uint lane [[thread_index_in_simdgroup]]) {
    uint v = lane * 10 + 1; // distinguishable per-lane value, never 0
    uint got = simd_shuffle(v, srcLane);
    out[tid] = got;
}
