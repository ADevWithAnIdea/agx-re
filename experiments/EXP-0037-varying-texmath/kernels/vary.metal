// EXP-0037 varying-store probe (OWN-SHADER). Bufferless full-screen triangle from
// vertex_id so tools/agxtest/agxrender can drive it (drawPrimitives vertexCount 3,
// no vertex buffer). Two float4 varyings with DISTINCT per-vertex gradients so the
// interpolated fragment output identifies which varying/slot the FS read and which
// source the VS store wrote. va = RGB gradient, vb = grayscale gradient.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float4 va;
    float4 vb;
};

// standard full-screen triangle: vid 0->(-1,-1) 1->(-1,3) 2->(3,-1) in clip space
static float2 tri(uint vid) {
    return float2((vid == 2) ? 3.0 : -1.0, (vid == 1) ? 3.0 : -1.0);
}

vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    o.pos = float4(tri(vid), 0.0, 1.0);
    // va: distinct per-vertex RGB so interpolation is a visible colour gradient
    o.va = float4(vid == 0 ? 0.90 : 0.10,
                  vid == 1 ? 0.90 : 0.10,
                  vid == 2 ? 0.90 : 0.10, 1.0);
    // vb: grayscale ramp, clearly different from va
    o.vb = float4(0.20 + 0.30 * vid, 0.20 + 0.30 * vid, 0.20 + 0.30 * vid, 1.0);
    return o;
}

// FS that outputs varying A (baseline: RGB gradient)
fragment float4 f_va(VOut in [[stage_in]]) { return in.va; }
// FS that outputs varying B (grayscale gradient) -- for comparison
fragment float4 f_vb(VOut in [[stage_in]]) { return in.vb; }
