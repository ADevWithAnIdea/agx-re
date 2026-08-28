#include <metal_stdlib>
using namespace metal;
// FS-08 remainder: is centroid interpolation behaviourally (not just structurally)
// distinct from center interpolation under PARTIAL sample coverage? Geometry: a single
// pixel (W=1,H=1,N=4) covered by exactly 2 of its 4 samples (pilot-confirmed via the
// resolve-fraction technique: NDC edge at x=-0.2 gives resolved fraction 0.5 at N=4,
// i.e. 2/4 samples covered), with the pixel's geometric CENTER (ndc_x=0.0) provably
// OUTSIDE the covered region (triangle covers only ndc_x<-0.2). The varying v is fed
// literally v=ndc_x per vertex, so its value is an EXACT, host-computable affine
// function of screen position everywhere (no ambiguity from an arbitrary plane).
// Oracle: v_center == 0.0 exactly (the true pixel-center ndc_x, extrapolated past the
// triangle edge); v_centroid must be < -0.2 (inside the actually-covered region, i.e.
// NOT equal to the extrapolated center value) if centroid genuinely clamps to coverage.
struct VOut { float4 pos [[position]]; float vc [[center_perspective]]; float vcen [[centroid_perspective]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-0.2, -1), float2(-0.2, 1), float2(-1, 0) };
    VOut o; o.pos = float4(p[vid], 0.0, 1.0); o.vc = p[vid].x; o.vcen = p[vid].x; return o;
}
fragment float4 f_main(VOut in [[stage_in]], device uint *buf [[buffer(0)]]) {
    buf[0] = as_type<uint>(in.vc);
    buf[1] = as_type<uint>(in.vcen);
    return float4(0,0,0,1);
}
