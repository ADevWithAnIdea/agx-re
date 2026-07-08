#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 col; float2 uv; };
struct VOutCent { float4 pos [[position]]; float4 col [[centroid_perspective]]; float2 uv; };
struct Vertex { float4 pos; float4 col; float2 uv; };

vertex VOut v_iso(uint vid [[vertex_id]], device const Vertex* vb [[buffer(0)]]) {
    VOut o; o.pos = vb[vid].pos; o.col = vb[vid].col; o.uv = vb[vid].uv; return o;
}
vertex VOutCent v_cent(uint vid [[vertex_id]], device const Vertex* vb [[buffer(0)]]) {
    VOutCent o; o.pos = vb[vid].pos; o.col = vb[vid].col; o.uv = vb[vid].uv; return o;
}
// centroid interpolation only
fragment float4 f_cent(VOutCent in [[stage_in]]) { return in.col; }
// single-channel dfdx only
fragment float4 f_deriv1(VOut in [[stage_in]]) { return float4(dfdx(in.uv.x), 0, 0, 1); }
// dfdx+dfdy+fwidth
fragment float4 f_derivf(VOut in [[stage_in]]) {
    float2 dx = dfdx(in.uv); float2 dy = dfdy(in.uv); float2 w = fwidth(in.uv);
    return float4(dx, dy) + float4(w, 0, 0) + in.col;
}
// single texture sample
fragment float4 f_tex1(VOut in [[stage_in]], texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv);
}
// programmable blend (tilebuffer read)
fragment float4 f_blend(VOut in [[stage_in]], float4 dst [[color(0)]]) {
    float a = in.col.a;
    return in.col * a + dst * (1.0 - a);
}
// interpolation only, NO color(0) -- to test if 54.. ops are iter (present) or tile-load (absent)
fragment float4 f_noblend(VOut in [[stage_in]]) {
    float a = in.col.a;
    return in.col * a + in.col * (1.0 - a);
}
