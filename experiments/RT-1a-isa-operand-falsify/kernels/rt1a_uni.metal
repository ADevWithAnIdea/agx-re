#include <metal_stdlib>
using namespace metal;
struct P { float k; };
kernel void k(device float* out [[buffer(0)]], const device float* a [[buffer(1)]],
              constant P& p [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + p.k;   // GPR + uniform
}
