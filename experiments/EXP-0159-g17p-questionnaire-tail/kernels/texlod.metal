// EXP-0159 FF carrier (TEX-01). Authored by the clean-room RE team.
//
// Explicit-level sample of a 4x4 R32Float texture with 3 mip levels whose
// texel value is 1000*level + 100*y + x, so a returned float NAMES the exact
// texel and mip level that was sampled.
//
// The coordinates and the third scalar operand are indexed by the thread id so
// the compiler cannot hoist them into the uniform/constant program: that is
// what makes it emit the `tex_addr_setup` instruction under test (a carrier
// with loop-invariant inputs compiles to a bare `tex_sample` with no address
// setup at all, and proves nothing -- see PRE_REGISTRATION and RESULTS).
//
// cin[0],cin[1] are the coordinates; cin[2] is the third scalar operand -- the
// LOD under the compiler's own encoding, the candidate projective divisor
// under the hypothesis being tested.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device const float* cin [[buffer(1)]],
              texture2d<float> tex [[texture(0)]],
              sampler smp [[sampler(0)]],
              uint gid [[thread_position_in_grid]]) {
  out[gid] = tex.sample(smp, float2(cin[3*gid], cin[3*gid+1]), level(cin[3*gid+2])).x;
}
