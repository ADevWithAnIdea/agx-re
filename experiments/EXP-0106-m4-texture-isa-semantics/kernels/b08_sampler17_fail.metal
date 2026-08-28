// EXP-0106 -- structural negative-compile probe for TEX-18. MSL's
// [[sampler(n)]] attribute is documented (and, per this project's own
// pre-freeze exploration, directly compiler-enforced) to require n in
// [0,15]. This file declares a 17th sampler argument and is EXPECTED to
// fail -[MTLDevice newLibraryWithSource:options:error:] -- the compile
// failure itself is the recorded observation (expect_status
// "library_failed"), not a harness defect.
#include <metal_stdlib>
using namespace metal;
kernel void k_b08_sampler17(texture2d<float> t [[texture(0)]], device float4* o [[buffer(0)]],
    sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]], sampler s2 [[sampler(2)]], sampler s3 [[sampler(3)]],
    sampler s4 [[sampler(4)]], sampler s5 [[sampler(5)]], sampler s6 [[sampler(6)]], sampler s7 [[sampler(7)]],
    sampler s8 [[sampler(8)]], sampler s9 [[sampler(9)]], sampler s10 [[sampler(10)]], sampler s11 [[sampler(11)]],
    sampler s12 [[sampler(12)]], sampler s13 [[sampler(13)]], sampler s14 [[sampler(14)]], sampler s15 [[sampler(15)]],
    sampler s16 [[sampler(16)]]) {
  float4 acc = float4(0);
  acc += t.sample(s0, float2(0.5)); acc += t.sample(s1, float2(0.5)); acc += t.sample(s2, float2(0.5));
  acc += t.sample(s3, float2(0.5)); acc += t.sample(s4, float2(0.5)); acc += t.sample(s5, float2(0.5));
  acc += t.sample(s6, float2(0.5)); acc += t.sample(s7, float2(0.5)); acc += t.sample(s8, float2(0.5));
  acc += t.sample(s9, float2(0.5)); acc += t.sample(s10, float2(0.5)); acc += t.sample(s11, float2(0.5));
  acc += t.sample(s12, float2(0.5)); acc += t.sample(s13, float2(0.5)); acc += t.sample(s14, float2(0.5));
  acc += t.sample(s15, float2(0.5)); acc += t.sample(s16, float2(0.5));
  o[0] = acc;
}
