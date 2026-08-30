// EXP-0159 FF carrier (TEX-01). Authored by the clean-room RE team.
// Explicit-level sample of a 4x4 R32Float texture with 3 mip levels whose
// texel value is 1000*level + 100*y + x, so a returned float NAMES the exact
// texel and mip level that was sampled. cin[0],cin[1] are the coordinates and
// cin[2] is the third scalar operand (the LOD under the compiler's own
// encoding; the candidate projective divisor under the hypothesis under test).
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device const float* cin [[buffer(1)]],
              texture2d<float> tex [[texture(0)]],
              sampler smp [[sampler(0)]]) {
  out[0] = tex.sample(smp, float2(cin[0], cin[1]), level(cin[2])).x;
}
