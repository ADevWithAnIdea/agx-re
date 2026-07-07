#include <metal_stdlib>
using namespace metal;
struct P { float k0, k1, k2, k3, k4, k5, k6, k7; };
kernel void k(device float* out [[buffer(0)]], const device float* a [[buffer(1)]],
              constant P& p [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + p.k0;   // GPR + uniform (single uniform src; sweep byte+1 to map index)
}
