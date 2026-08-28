// fsorder.metal -- EXP-0117 FS output-ordering-constraints probe (OWN-SHADER).
//
// MSL fragment outputs are a single struct return (color/depth/stencil/
// sample_mask members), so there is no explicit "instruction order" of
// writes at the source level the way GLSL's separate gl_FragDepth/
// gl_FragColor assignments imply one. What IS testable: (a) whether the
// SOURCE order in which struct fields are computed/assigned changes the
// compiled code or the hardware result (it should not, if the struct
// return is a single atomic commit); (b) whether a fixed-function DEPTH
// TEST failure (using the shader's OWN explicit depth output, not the
// built-in rasterizer depth) suppresses color+stencil writes and, when the
// stencil op differs by depth pass/fail, whether the CORRECT op is
// selected against the POST-shader depth value.

#include <metal_stdlib>
using namespace metal;

// Two disjoint screen halves (left: NDC x<0, right: NDC x>=0), like
// EXP-0111's poscoord_xhalf technique -- a single draw, two independently
// readable regions, one fixed-function depth-stencil state.
vertex float4 v_half(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid % 3], 0.0, 1.0);
}

struct FSOut { float4 c0 [[color(0)]]; float d [[depth(less)]]; uint s [[stencil]]; };
// params: x=passDepth, y=failDepth, z=window-space X threshold (== target
// width/2; NOT a hardcoded literal, since the split must work at any --w).

// f_order_ab: source-order color, then depth, then stencil.
fragment FSOut f_order_ab(float4 pos [[position]], constant float3 &params [[buffer(0)]]) {
    float4 c = float4(1,1,1,1);
    float d = (pos.x < params.z) ? params.x : params.y; // left half passes, right half fails (harness picks values s.t. this holds)
    uint s = 222u;
    FSOut o; o.c0 = c; o.d = d; o.s = s; return o;
}
// f_order_ba: IDENTICAL result, but computed and assigned in the OPPOSITE
// source order (stencil, then depth, then color) -- same final values.
fragment FSOut f_order_ba(float4 pos [[position]], constant float3 &params [[buffer(0)]]) {
    uint s = 222u;
    float d = (pos.x < params.z) ? params.x : params.y;
    float4 c = float4(1,1,1,1);
    FSOut o; o.s = s; o.d = d; o.c0 = c; return o;
}

// Combined suppression + stencil-op-selection probe: left half's shader
// depth is engineered by the HARNESS to PASS the configured compare
// function, right half's to FAIL it. Stencil test is held at Always (so
// stencil-op selection depends purely on the depth-test outcome), and the
// two ops (depthFailOperation vs depthStencilPassOperation) are configured
// DIFFERENTLY by the harness so the readback distinguishes which one fired.
// Color/stencil suppression on the FAIL side is checked by comparing
// against the clear values (nothing this shader wrote should be visible if
// suppression is real and total, matching EXP-0109 Sec 3.3/3.4 and EXP-0091's
// discard-suppression precedent, now for a REAL depth-test fail, not discard).
fragment FSOut f_fsorder_probe(float4 pos [[position]], constant float3 &params [[buffer(0)]]) {
    FSOut o;
    o.c0 = float4(1,1,1,1);
    o.d = (pos.x < params.z) ? params.x : params.y;
    o.s = 222u; // deliberately different from both the clear stencil and any encode-time ref
    return o;
}
