// Mixed fetch: one stage_in attribute (descriptor-driven prologue fetch) PLUS a
// manual [[vertex_id]]/[[instance_id]]-indexed device buffer load in the body.
#include <metal_stdlib>
using namespace metal;
struct VIn  { float4 pos [[attribute(0)]]; };
struct VOut { float4 pos [[position]]; float4 v; };
vertex VOut vMain(VIn in [[stage_in]], uint vid [[vertex_id]], uint iid [[instance_id]],
                  device const float4* extra [[buffer(4)]]) {
    VOut o; o.pos = in.pos + extra[vid]; o.v = extra[iid] * in.pos; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
