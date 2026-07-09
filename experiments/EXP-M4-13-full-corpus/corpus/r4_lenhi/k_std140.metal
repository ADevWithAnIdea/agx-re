#include <metal_stdlib>
using namespace metal;
// Mimic Dawn std140 uniform->storage: read padded columns from a constant buffer,
// write tightly-packed to a storage buffer. Many matrices force high register use.
struct M2 { float2 col0; float _p0[2]; float2 col1; float _p1[2]; };
struct U { M2 m[16]; uint dyn; };
struct Out { float2 col0; float2 col1; };
kernel void k(device Out* dst [[buffer(0)]],
              constant U& u [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    uint idx = (tid + u.dyn) & 15u;
    for (uint k=0;k<16;k++){
        uint j=(k+idx)&15u;
        dst[k].col0 = u.m[j].col0;
        dst[k].col1 = u.m[(j*3u+idx)&15u].col1;
    }
}
