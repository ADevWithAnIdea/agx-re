// EXP-0106 -- structural negative-compile probe for TEX-05. Per the public
// MSL spec's 2D-texture sample() overload set (section 6.12.3), only
// bias(...) and gradient2d(...) combine with min_lod_clamp(...) in a single
// call; there is no such combined overload for level(...). This file is
// EXPECTED to fail -[MTLDevice newLibraryWithSource:options:error:] -- the
// compile failure itself is the recorded observation (see CAPTURE_CONTRACT
// expect_status "library_failed"), not a harness defect.
#include <metal_stdlib>
using namespace metal;
kernel void k_b04_level_minlod(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    device uint* out [[buffer(0)]]) {
  out[0] = t.sample(s, float2(0.5, 0.5), level(2.0), min_lod_clamp(1.0)).x;
}
