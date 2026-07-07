// EXP-0036 census corpus — RENDER (vertex+fragment) pipelines (OWN-SHADER).
// Vertex data is fetched in-shader from a buffer indexed by [[vertex_id]] (so no
// MTLVertexDescriptor is needed by the harness; this is exactly the in-shader
// vertex-fetch path, EXP-0031). Covers vertex varying stores, perspective/flat/
// centroid interpolation, fragment texture sampling (implicit LOD -> derivatives),
// dfdx/dfdy, and programmable blend (tilebuffer read).
#include <metal_stdlib>
using namespace metal;

struct Vertex { float4 pos; float4 col; float2 uv; };
struct VOut     { float4 pos [[position]]; float4 col; float2 uv; };
struct VOutFlat { float4 pos [[position]]; float4 col [[flat]]; float2 uv; };
struct VOutCent { float4 pos [[position]]; float4 col [[centroid_perspective]]; float2 uv; };

// ---- basic transform + interpolated colour ----
vertex VOut v_basic(uint vid [[vertex_id]], device const Vertex* vb [[buffer(0)]],
                    constant float4x4& mvp [[buffer(1)]]) {
    VOut o; o.pos = mvp * vb[vid].pos; o.col = vb[vid].col; o.uv = vb[vid].uv; return o;
}
fragment float4 f_basic(VOut in [[stage_in]]) { return in.col; }

// ---- flat-shaded varying ----
vertex VOutFlat v_flat(uint vid [[vertex_id]], device const Vertex* vb [[buffer(0)]]) {
    VOutFlat o; o.pos = vb[vid].pos; o.col = vb[vid].col; o.uv = vb[vid].uv; return o;
}
fragment float4 f_flat(VOutFlat in [[stage_in]]) { return in.col; }

// ---- centroid interpolation ----
vertex VOutCent v_cent(uint vid [[vertex_id]], device const Vertex* vb [[buffer(0)]]) {
    VOutCent o; o.pos = vb[vid].pos; o.col = vb[vid].col; o.uv = vb[vid].uv; return o;
}
fragment float4 f_cent(VOutCent in [[stage_in]]) { return in.col; }

// ---- fragment texture sample (implicit LOD => derivatives in the tex unit) ----
fragment float4 f_tex(VOut in [[stage_in]], texture2d<float> t [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv) * in.col;
}

// ---- explicit derivatives (dfdx/dfdy/fwidth) ----
fragment float4 f_deriv(VOut in [[stage_in]]) {
    float2 dx = dfdx(in.uv); float2 dy = dfdy(in.uv); float2 w = fwidth(in.uv);
    return float4(dx, dy) + float4(w, 0, 0) + in.col;
}

// ---- programmable blend: read the current tilebuffer colour ([[color(0)]] input) ----
fragment float4 f_blend(VOut in [[stage_in]], float4 dst [[color(0)]]) {
    float a = in.col.a;
    return in.col * a + dst * (1.0 - a);
}
