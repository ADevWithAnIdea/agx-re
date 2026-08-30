// EXP-0159 FD carrier (TEX-21/TEX-22). Authored by the clean-room RE team.
//
// A bindless sampler heap declared at SCAP entries, indexed by a genuinely
// runtime uint, plus a DIRECTLY-BOUND sampler kernel used as an
// independent-path oracle: each canary sampler's "fingerprint" (the float it
// makes the sample return) is first measured through [[sampler(0)]], and the
// bindless heap must then reproduce that same fingerprint at that index.
//
// The bound texture is 4x4 R32Float with 3 mip levels, texel = 1000*L+100*y+x.
// The sample coordinate is (1.2, 1.2) -- deliberately OUTSIDE [0,1] -- at
// explicit level(2.0), so a sampler's address modes and lodMaxClamp both move
// the result:  six canary classes give six DISTINCT non-zero fingerprints
// (303, 300, 3, 1101, 1100, 1001), which is what lets a wrong entry, an
// unpopulated entry and a default sampler be told apart.
#include <metal_stdlib>
using namespace metal;
#define SCAP 500000
struct SHeap { array<sampler, SCAP> s [[id(0)]]; };

kernel void k_direct(device float* out [[buffer(0)]],
                     texture2d<float> tex [[texture(0)]],
                     sampler smp [[sampler(0)]]) {
  out[0] = tex.sample(smp, float2(1.2f, 1.2f), level(2.0f)).x;
}
kernel void k_samp(constant SHeap& h [[buffer(0)]],
                   constant uint& idx [[buffer(1)]],
                   device float* out [[buffer(2)]],
                   texture2d<float> tex [[texture(0)]]) {
  out[0] = tex.sample(h.s[idx], float2(1.2f, 1.2f), level(2.0f)).x;
}
kernel void k_samp_perlane(constant SHeap& h [[buffer(0)]],
                           device const uint* idxs [[buffer(1)]],
                           device float* out [[buffer(2)]],
                           texture2d<float> tex [[texture(0)]],
                           uint t [[thread_position_in_grid]]) {
  out[t] = tex.sample(h.s[idxs[t]], float2(1.2f, 1.2f), level(2.0f)).x;
}
