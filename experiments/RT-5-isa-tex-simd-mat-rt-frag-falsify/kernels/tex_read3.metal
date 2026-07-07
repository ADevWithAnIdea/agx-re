#include <metal_stdlib>
using namespace metal;
// 3 distinct solid textures. out[i] = t_i.read(0,0). Splice sample#0's op+4
// (tex_slot) to map which value selects which texture.
kernel void k(texture2d<float> t0 [[texture(0)]],
              texture2d<float> t1 [[texture(1)]],
              texture2d<float> t2 [[texture(2)]],
              device float4* out  [[buffer(0)]]) {
    out[0] = t0.read(uint2(0,0));
    out[1] = t1.read(uint2(0,0));
    out[2] = t2.read(uint2(0,0));
}
