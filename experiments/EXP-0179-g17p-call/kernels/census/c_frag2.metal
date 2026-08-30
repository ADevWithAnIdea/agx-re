// EXP-0179 census EXTENSION (run `census_*_ext`, NOT part of the 24 frozen in
// CAPTURE_CONTRACT.json -- added after run `census_20260830a` returned NO call
// from either render stage, which is directly on P0.8's VS/FS/CS row).
// CLEAN-ROOM: our own MSL. Per-construct outcomes only; Apple's inlining
// heuristic remains a declared boundary and is not characterised.
#include <metal_stdlib>
using namespace metal;

struct VOut2 { float4 pos [[position]]; float2 uv; };

// C25/C26: a LARGE noinline helper on each render stage. c_frag.metal's helper
// was four multiplies; this one is a long dependent chain.
__attribute__((noinline))
static float4 big_help(float2 uv, float k) {
    float a = uv.x, b = uv.y, c = k;
    for (int i = 0; i < 48; ++i) {
        a = fma(a, 1.03f, b);
        b = fma(b, 0.97f, c);
        c = fma(c, 1.01f, a);
    }
    return float4(a, b, c, a + b + c);
}

vertex VOut2 v_big(uint vid [[vertex_id]], constant float& k [[buffer(0)]]) {
    VOut2 o;
    float2 p = float2((vid == 2) ? 3.0f : -1.0f, (vid == 1) ? 3.0f : -1.0f);
    float4 r = big_help(p, k);
    o.pos = float4(p, 0.0f, 1.0f) + r * 0.0001f;
    o.uv = p * 0.5f + 0.5f;
    return o;
}

fragment float4 f_big(VOut2 in [[stage_in]], constant float& k [[buffer(0)]]) {
    return big_help(in.uv, k);
}
