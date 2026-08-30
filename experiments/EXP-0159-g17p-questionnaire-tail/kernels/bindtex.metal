// EXP-0159 FC carrier (TEX-19). Authored by the clean-room RE team.
// A 1,000,000-entry argument-buffer texture array, indexed by a genuinely
// runtime uint. k_uniform takes one index for the whole dispatch; k_perlane
// gives every lane its own index, so per-lane divergent bindless selection is
// exercised at the same magnitudes.
#include <metal_stdlib>
using namespace metal;
#define CAP 1000000
struct AB { array<texture2d<uint>, CAP> tex [[id(0)]]; };

kernel void k_uniform(constant AB& ab [[buffer(0)]],
                      constant uint& idx [[buffer(1)]],
                      device uint* out [[buffer(2)]]) {
  out[0] = ab.tex[idx].read(uint2(0, 0)).x;
}
kernel void k_perlane(constant AB& ab [[buffer(0)]],
                      device const uint* idxs [[buffer(1)]],
                      device uint* out [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
  out[t] = ab.tex[idxs[t]].read(uint2(0, 0)).x;
}
