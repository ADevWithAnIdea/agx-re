// Vertex amplification: [[amplification_id]] / [[amplification_count]] inputs.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 v; };
vertex VOut vMain(uint vid [[vertex_id]],
                  ushort ampid  [[amplification_id]],
                  ushort ampcnt [[amplification_count]],
                  device const float4* vb [[buffer(0)]]) {
    VOut o; o.pos = vb[vid] + float4(float(ampid) * 0.01, 0, 0, 0);
    o.v = float4(float(ampcnt)); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
