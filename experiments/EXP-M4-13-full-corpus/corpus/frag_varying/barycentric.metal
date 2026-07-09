// frag_varying: EXTRAPOLATION -> Family-9 barycentric_coord + primitive_id reads.
// If the compiler accepts these, the HW exposes raw barycentrics for manual interp;
// a compile failure is a first-class NEGATIVE result (feature not exposed via MSL).
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 a; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; return o;
}
fragment float4 fMain(VOut in [[stage_in]],
                      float3 bc   [[barycentric_coord]],
                      uint   prim [[primitive_id]]) {
    return in.a * bc.x + float4(bc, float(prim));
}
