#include <metal_stdlib>
using namespace metal;
// GLFS-A01 splice target (revised): a runtime (buffer-sourced, non-foldable)
// sample_mask write at sampleCount=1. Depth uses ordinary FIXED-FUNCTION
// (rasterizer-interpolated) depth from a constant vertex z=0.1, not a shader depth
// output, so this compiles without a depth-attachment format being known at
// archive-build time (shdump's validation pipeline has none). depth-compare is set
// to Always by the harness so occlusion/depth are gated purely by the kill
// mechanism, not a geometric test. Readback: color + depth + occlusion count triply
// corroborate the located submission op's effect.
struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.1, 1.0); return o;
}
fragment FOut f_main(constant uint &wantmask [[buffer(0)]]) {
    FOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.mask = wantmask;
    return o;
}
