// EXP-0159 FF array-coordinate carrier (TEX-01).
// A 4x4 R32Float 2D ARRAY texture, 3 layers, texel = 1000*layer + 100*y + x.
// The third coordinate is a genuine array layer here, so the same `form` sweep
// tells us what form 0x01 does to an array-coordinate operand.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device const float* cin [[buffer(1)]],
              texture2d_array<float> tex [[texture(0)]],
              sampler smp [[sampler(0)]]) {
  out[0] = tex.sample(smp, float2(cin[0], cin[1]), uint(cin[2])).x;
}
