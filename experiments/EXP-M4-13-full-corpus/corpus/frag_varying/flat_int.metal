// frag_varying: FLAT interpolation of integer varyings (integers must be flat).
// Isolates the no-interpolation flat-load path for int/uint scalar+vector.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    uint4 u [[flat]];
    int   j [[flat]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const uint4* vin [[buffer(0)]]) {
    VOut o; o.pos = float4(vin[vid]); o.u = vin[vid]; o.j = int(vid); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) {
    uint4 s = in.u + uint4(uint(in.j));   // forces the flat integer loads
    return float4(s);
}
