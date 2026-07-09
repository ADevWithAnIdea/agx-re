#include <metal_stdlib>
using namespace metal;
// Clean-room render probe: provoke the 8-byte low-nibble-9 op-select 0x2f/0x3f/0x0f
// family (heavy in fragment/vertex/varying code). Our own MSL.

struct VOut { float4 pos [[position]]; float4 c; float2 uv; };

vertex VOut v_main(uint vid [[vertex_id]],
                   device const float4* p [[buffer(0)]],
                   device const float4* col [[buffer(1)]]) {
    VOut o;
    o.pos = p[vid];
    o.c   = col[vid] * 2.0f;      // scale attribute -> mul in VS
    o.uv  = p[vid].xy + col[vid].zw;
    return o;
}

// pure passthrough interpolated color
fragment float4 f_color(VOut in [[stage_in]]) {
    return in.c;
}

// perspective interpolation then use -> likely the mystery op
fragment float4 f_scale(VOut in [[stage_in]]) {
    return in.c * in.uv.x;
}

// derivative in fragment
fragment float4 f_deriv(VOut in [[stage_in]]) {
    float2 d = dfdx(in.uv) + dfdy(in.uv);
    return float4(d, fwidth(in.uv.x), 1.0);
}

// two-varying combine
fragment float4 f_combine(VOut in [[stage_in]]) {
    return in.c + float4(in.uv, 0.0, 0.0);
}
