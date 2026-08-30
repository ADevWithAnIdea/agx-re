// EXP-0159 FD carrier (TEX-21/TEX-22). Authored by the clean-room RE team.
// A bindless sampler heap declared at the published Metal ceiling
// (maxArgumentBufferSamplerCount = 500000), indexed by a genuinely runtime
// uint. EXP-O2B proved a hand-written tightly-packed array of 8-byte
// gpuResourceIDs is byte-identical to MTLArgumentEncoder's output for
// `array<sampler,K>`, so the heap buffer is built directly and an arbitrary
// (including out-of-table) ID can be placed in any entry.
//
// The returned float NAMES which sampler ran: sampling the authored 2x2
// R32Float texture (texels 0,2,4,6) at the exact centre gives 3.0 under
// linear filtering and one of 0/2/4/6 under nearest, so filter identity is
// directly observable in the read-back value.
#include <metal_stdlib>
using namespace metal;
#define SCAP 500000
struct SHeap { array<sampler, SCAP> s [[id(0)]]; };

kernel void k_samp(constant SHeap& h [[buffer(0)]],
                   constant uint& idx [[buffer(1)]],
                   device float* out [[buffer(2)]],
                   texture2d<float> tex [[texture(0)]]) {
  out[0] = tex.sample(h.s[idx], float2(0.5f, 0.5f)).x;
}
kernel void k_samp_perlane(constant SHeap& h [[buffer(0)]],
                           device const uint* idxs [[buffer(1)]],
                           device float* out [[buffer(2)]],
                           texture2d<float> tex [[texture(0)]],
                           uint t [[thread_position_in_grid]]) {
  out[t] = tex.sample(h.s[idxs[t]], float2(0.5f, 0.5f)).x;
}
