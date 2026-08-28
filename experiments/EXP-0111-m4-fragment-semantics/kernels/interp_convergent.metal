#include <metal_stdlib>
using namespace metal;
// FS-09: does a "convergent" interpolated input (all 3 vertices carry the IDENTICAL
// attribute value, so the true mathematical result is that constant everywhere) remain
// bit-exactly distinct from a flat (provoking-vertex) load of the same value, or does the
// hardware/compiler special-case it into an exact flat-equivalent load? Per-vertex w
// values (buffer(2).xyz) force genuinely different perspective divisors across the
// triangle (so the smooth-perspective path performs real, non-trivial rcp/fmul
// arithmetic per EXP-0029's documented lowering) while the attribute itself (buffer(2).w)
// is identical at all three vertices -- so any bit-level deviation from the flat value is
// attributable purely to interpolation-path floating-point rounding, not a genuine value
// difference. w/attribute values are runtime uniforms so one kernel serves a sweep.
struct VOut { float4 pos [[position]];
              float vflat [[flat]];
              float vsmooth [[center_perspective]];
              float vlinear [[center_no_perspective]]; };
vertex VOut v_main(uint vid [[vertex_id]], constant float4 &params [[buffer(2)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    float w[3] = { params.x, params.y, params.z };
    float attr = params.w;
    VOut o;
    o.pos = float4(p[vid]*w[vid], 0.0, w[vid]);   // clip-space xy pre-multiplied by w so
                                                    // NDC xy after the divide is unchanged
                                                    // (same screen geometry as every other
                                                    // kernel here) while w itself varies.
    o.vflat = attr; o.vsmooth = attr; o.vlinear = attr;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]],
                        device uint *buf [[buffer(0)]], constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)in.pos.x, py = (uint)in.pos.y;
    uint idx = py * dims.x + px;
    buf[idx*3+0] = as_type<uint>(in.vflat);
    buf[idx*3+1] = as_type<uint>(in.vsmooth);
    buf[idx*3+2] = as_type<uint>(in.vlinear);
    return float4(0,0,0,1);
}
