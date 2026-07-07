#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device int4* pout [[buffer(1)]],
              const device int4* v [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
    int4 p = v[gid];
    out[gid] = p.x - p.y;   // isub
    pout[gid] = p;
}
