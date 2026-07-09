#include <metal_stdlib>
using namespace metal;
// Several INDEPENDENT arithmetic-shift-right-by-immediate results live at once ->
// distinct dst registers. Probes the 0xa7 10-byte "ishift" byte+5 hole: does
// byte+5 track the destination/source register (reg<<1) or the shift amount?
kernel void k_ashr_dst(device int4* out [[buffer(0)]],
                       device const int* a [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    int s0 = a[gid+0] >> 2;
    int s1 = a[gid+1] >> 2;
    int s2 = a[gid+2] >> 2;
    int s3 = a[gid+3] >> 2;
    out[gid] = int4(s0, s1, s2, s3);
}
