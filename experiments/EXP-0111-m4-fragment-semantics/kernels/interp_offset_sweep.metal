#include <metal_stdlib>
using namespace metal;
// FS-08 remainder: numeric validation of interpolate_at_offset against a host-computable
// exact affine varying (v = ndc_x, same technique as interp_centroid_extrap.metal), full
// coverage (N=1) so there is no coverage-clamping confound -- isolates the OFFSET math
// itself. Oracle: value at offset (dx,dy) == plane evaluated at the pixel center shifted
// by (dx,dy) in pixel units == ndc_x_at(px+0.5+dx, py+0.5+dy) (dy is irrelevant here since
// v depends only on x, but is swept anyway to confirm the y-offset is honoured/inert as
// expected). The exact offset (in pixel units, buffer(1)) is supplied at runtime so one
// kernel serves the whole sweep. Vertex and fragment use SEPARATE struct types: the
// vertex stage writes a plain float; the fragment stage opts into pull-model access via
// interpolant<float,...> at the SAME [[user(locn0)]] slot (MSL 6.11 pull-model contract).
struct VOut { float4 pos [[position]]; float v [[user(locn0)]]; };
struct FIn  { float4 pos [[position]]; interpolant<float, interpolation::perspective> v [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.v = p[vid].x; return o;
}
fragment float4 f_main(FIn in [[stage_in]], device uint *buf [[buffer(0)]],
                        constant float2 &offset [[buffer(1)]]) {
    float v_off = in.v.interpolate_at_offset(offset);
    buf[0] = as_type<uint>(v_off);
    return float4(0,0,0,1);
}
