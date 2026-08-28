#include <metal_stdlib>
using namespace metal;
kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device int *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    int m = max(a[gid], b[gid]);
    int n = min(a[gid], b[gid]);
    int p = m + n;
    int q = m - n;
    out[gid] = m;
    out[gid+4] = n;
    out[gid+8] = p;
    out[gid+12] = q;
}
