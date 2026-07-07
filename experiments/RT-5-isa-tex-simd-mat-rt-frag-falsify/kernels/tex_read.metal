#include <metal_stdlib>
using namespace metal;

// Texture READ (no sampler): out[0] = t0.read(0,0); out[1] = t1.read(0,0).
// Tests the read variant (op+2 = 0x17) and tex_slot selection.
kernel void k(texture2d<float> t0 [[texture(0)]],
              texture2d<float> t1 [[texture(1)]],
              device float4* out  [[buffer(0)]]) {
    out[0] = t0.read(uint2(0,0));
    out[1] = t1.read(uint2(0,0));
}
