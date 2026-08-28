#include <metal_stdlib>
using namespace metal;
kernel void cs_tg(device uint* out [[buffer(0)]],
                   uint tid [[thread_position_in_grid]],
                   uint tew [[thread_execution_width]],
                   uint lane [[thread_index_in_simdgroup]]) {
    out[tid] = tew * 1000 + lane;
}
