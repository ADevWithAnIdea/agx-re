// conversions_pack: SPECULATIVE probe for an sRGB pack intrinsic.
// Hypothesis: MSL exposes pack_float_to_srgb_unorm4x8 mirroring the unorm packers.
// If this fails to compile, that is a first-class NEGATIVE result (no such intrinsic).
#include <metal_stdlib>
using namespace metal;
kernel void pack_srgb_builtin(device uint* o [[buffer(0)]],
                              device const float4* fa [[buffer(1)]],
                              uint i [[thread_position_in_grid]]) {
    o[i] = pack_float_to_srgb_unorm4x8(fa[i]);
}
