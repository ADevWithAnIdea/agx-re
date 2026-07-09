// conversions_pack: SPECULATIVE probe for an RGB9E5 pack intrinsic.
// Hypothesis: MSL exposes pack_float_to_rgb9e5 (shared-exponent pack).
// If this fails to compile, that is a first-class NEGATIVE result.
#include <metal_stdlib>
using namespace metal;
kernel void pack_rgb9e5_builtin(device uint* o [[buffer(0)]],
                                device const float3* fa [[buffer(1)]],
                                uint i [[thread_position_in_grid]]) {
    o[i] = pack_float_to_rgb9e5(fa[i]);
}
