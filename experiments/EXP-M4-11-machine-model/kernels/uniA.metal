#include <metal_stdlib>
using namespace metal;
struct P { float k; };
kernel void k(device float* out [[buffer(0)]],
              device const float* a [[buffer(1)]],
              constant P& p [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = p.k + a[gid];   // uniform as srcA
}
