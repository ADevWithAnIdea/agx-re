#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out    [[buffer(0)]],
              device int4* pout  [[buffer(1)]],
              device int4* qout  [[buffer(2)]],
              const device int4* v [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    int4 p = v[gid*2+0];
    int4 q = v[gid*2+1];
    out[gid]  = p.x + p.y;   // clean exposed iadd2
    pout[gid] = p;
    qout[gid] = q;
}
