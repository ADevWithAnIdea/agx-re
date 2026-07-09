// frag_varying: FLAT interpolation of FLOAT varyings (provoking-vertex value, no interp).
// Isolates flat-load of float scalar/vec vs the perspective iterate path.
#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 pos [[position]];
    float4 a [[flat]];
    float  b [[flat]];
};
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; o.b = vin[vid].w; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.a + in.b; }
