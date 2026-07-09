// frag_varying: hardware fragment special registers alongside a user varying:
// [[position]] frag-coord, [[front_facing]], [[sample_id]], [[sample_mask]].
// Isolates the special-register reads that drive/interact with per-sample interp.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 a; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vin [[buffer(0)]]) {
    VOut o; o.pos = vin[vid]; o.a = vin[vid]; return o;
}
struct FIn {
    float4 fc  [[position]];       // frag-coord special reg
    float4 a;                      // user center-perspective varying
};
fragment float4 fMain(FIn in [[stage_in]],
                      bool ff  [[front_facing]],
                      uint sid [[sample_id]],
                      uint cov [[sample_mask]]) {
    float f = ff ? 1.0f : -1.0f;
    return in.a + in.fc + float4(float(sid), float(cov), f, 0.0f);
}
