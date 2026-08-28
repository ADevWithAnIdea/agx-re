// EXP-0106 -- structural negative-compile probe for TEX-05. The public MSL
// spec's gather() overload set (section 6.12.6) takes at most 4 arguments
// (sampler, coord, offset, component) with no lod_options/min_lod_clamp
// slot at all. This file is EXPECTED to fail
// -[MTLDevice newLibraryWithSource:options:error:] -- the compile failure
// itself is the recorded observation (expect_status "library_failed").
#include <metal_stdlib>
using namespace metal;
kernel void k_b04_gather_minlod(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    device uint* out [[buffer(0)]]) {
  out[0] = t.gather(s, float2(0.5, 0.5), int2(0), component::x, min_lod_clamp(1.0)).x;
}
