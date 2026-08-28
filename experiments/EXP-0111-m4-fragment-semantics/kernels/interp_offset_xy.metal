#include <metal_stdlib>
using namespace metal;
// Pilot diagnostic only: v depends on BOTH x and y (v=ndc_x+10*ndc_y so the two axes are
// separable in the readback), cross-checking the "absolute window-space corner-relative
// coordinate, y-down" hypothesis derived from the separate X-only/Y-only diagnostics.
struct VOut { float4 pos [[position]]; float v0 [[user(locn0)]]; float v1 [[user(locn1)]]; };
struct FIn  { float4 pos [[position]];
              float vpush [[user(locn0)]];
              interpolant<float, interpolation::perspective> vpull [[user(locn1)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1);
    float val = p[vid].x + 10.0*p[vid].y;
    o.v0 = val; o.v1 = val; return o;
}
fragment float4 f_main(FIn in [[stage_in]], device uint *buf [[buffer(0)]],
                        constant float2 &offset [[buffer(1)]]) {
    float c = in.vpull.interpolate_at_offset(offset);
    buf[0] = as_type<uint>(c);
    return float4(0,0,0,1);
}
