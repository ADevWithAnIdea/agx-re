#include <metal_stdlib>
using namespace metal;

// Two textures, two samplers. out[0] = t0 via s0; out[1] = t1 via s1.
// Both textures/samplers are genuinely bound & slotted (slot0/slot1).
// The FIRST sample op encodes tex_slot=0, samp_slot=0; splicing its op+4/op+5
// should redirect it to t1 / s1 and change out[0].
kernel void k(texture2d<float> t0 [[texture(0)]],
              texture2d<float> t1 [[texture(1)]],
              sampler s0          [[sampler(0)]],
              sampler s1          [[sampler(1)]],
              device float4* out  [[buffer(0)]]) {
    out[0] = t0.sample(s0, float2(0.5f, 0.5f));
    out[1] = t1.sample(s1, float2(0.5f, 0.5f));
}
