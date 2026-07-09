#include <metal_stdlib>
using namespace metal;
kernel void k_sr(device uint* out [[buffer(0)]],
                 uint tid [[thread_position_in_grid]],
                 uint tpg [[threads_per_grid]],
                 uint sgid [[thread_index_in_simdgroup]],
                 uint sgsz [[threads_per_simdgroup]]) {
    out[tid] = tid + tpg + sgid + sgsz;
}
