// msaa_diff.metal -- EXP-0117 MSAA-dependent centroid-vs-sample VALUE
// differentiation (OWN-SHADER). EXP-0111 FS-08 left this PARTIAL: it showed
// centroid and sample BOTH differ from (unclamped) center, but did not show
// sample and centroid differ from EACH OTHER. This reuses EXP-0111's
// PROVEN partial-coverage geometry (interp_centroid_extrap.metal: single
// pixel, N=4, triangle edge at NDC x=-0.2, exactly 2 of 4 samples covered,
// pixel center at ndc_x=0.0 strictly OUTSIDE coverage) and captures EVERY
// per-sample invocation's (sample_id, sample-value, centroid-value,
// center-value) via an atomic-append SSBO record so per-invocation
// divergence is directly observable (not just a single racing buffer slot).

#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; float v; };
struct FIn  { float4 pos [[position]]; interpolant<float, interpolation::perspective> v; };

vertex VOut v_msaadiff(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-0.2, -1), float2(-0.2, 1), float2(-1, 0) };
    VOut o; o.pos = float4(p[vid], 0.0, 1.0); o.v = p[vid].x; return o;
}

struct Rec { uint sid; float vsample; float vcentroid; float vcenter; };
fragment float4 f_msaadiff(FIn in [[stage_in]], uint sid [[sample_id]],
                            device Rec *out [[buffer(0)]],
                            device atomic_uint *counter [[buffer(1)]]) {
    uint idx = atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    Rec r;
    r.sid = sid;
    r.vsample = in.v.interpolate_at_sample(sid);
    r.vcentroid = in.v.interpolate_at_centroid();
    r.vcenter = in.v.interpolate_at_center();
    out[idx] = r;
    return float4(0,0,0,1);
}
