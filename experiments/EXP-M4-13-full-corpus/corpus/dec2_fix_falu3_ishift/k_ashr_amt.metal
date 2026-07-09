#include <metal_stdlib>
using namespace metal;
// Same source, four DIFFERENT shift amounts -> isolates byte+6 (shamt) from byte+5.
kernel void k_ashr_amt(device int4* out [[buffer(0)]],
                       device const int* a [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    int v = a[gid];
    out[gid] = int4(v>>1, v>>2, v>>4, v>>8);
}
