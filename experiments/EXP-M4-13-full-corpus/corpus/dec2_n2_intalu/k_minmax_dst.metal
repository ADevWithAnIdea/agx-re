#include <metal_stdlib>
using namespace metal;
// HIGH-NIBBLE TEST: 8 independent integer min results, all live simultaneously,
// combined only at the end so the compiler must allocate 8 distinct dst regs.
kernel void k_minmax_dst(device int* out [[buffer(0)]],
                         device const int* a [[buffer(1)]],
                         device const int* b [[buffer(2)]],
                         uint gid [[thread_position_in_grid]]) {
    int r0 = min(a[gid+0], b[gid+0]);
    int r1 = min(a[gid+1], b[gid+1]);
    int r2 = min(a[gid+2], b[gid+2]);
    int r3 = min(a[gid+3], b[gid+3]);
    int r4 = min(a[gid+4], b[gid+4]);
    int r5 = min(a[gid+5], b[gid+5]);
    int r6 = min(a[gid+6], b[gid+6]);
    int r7 = min(a[gid+7], b[gid+7]);
    // keep all live to end
    out[gid+0] = r0; out[gid+1] = r1; out[gid+2] = r2; out[gid+3] = r3;
    out[gid+4] = r4; out[gid+5] = r5; out[gid+6] = r6; out[gid+7] = r7;
}
