#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out   [[buffer(0)]],
              device float4* pout [[buffer(1)]],
              device float4* qout [[buffer(2)]],
              const device float4* v [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    float4 p = v[gid*2+0];
    float4 q = v[gid*2+1];
    out[gid]  = p.x + p.y;   // clean exposed falu2
    pout[gid] = p;           // keep p.x..w live (raw)
    qout[gid] = q;           // keep q.x..w live (raw)
}
