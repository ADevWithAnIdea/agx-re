// frag_varying: point-sprite [[point_coord]] fragment input (special interpolated reg).
// Isolates the hardware-provided point-coordinate read distinct from user varyings.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float ps [[point_size]]; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.ps = 8.0f; return o;
}
fragment float4 fMain(float2 pc [[point_coord]]) {
    return float4(pc, 1.0f - pc.x, 1.0f);
}
