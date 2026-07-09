// conversions_pack: SPECULATIVE probe for an R11G11B10-float pack intrinsic.
// Hypothesis: MSL exposes pack_float_to_r11g11b10f (packed small-float pack).
// If this fails to compile, that is a first-class NEGATIVE result.
#include <metal_stdlib>
using namespace metal;
kernel void pack_r11g11b10_builtin(device uint* o [[buffer(0)]],
                                   device const float3* fa [[buffer(1)]],
                                   uint i [[thread_position_in_grid]]) {
    o[i] = pack_float_to_r11g11b10f(fa[i]);
}
