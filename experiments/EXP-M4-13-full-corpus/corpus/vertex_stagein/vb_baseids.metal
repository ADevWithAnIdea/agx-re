// [[base_vertex]] / [[base_instance]] system values: reconstruct gl-style
// VertexIndex/InstanceIndex (absolute id minus base) => surfaces base subtraction.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 v; };
vertex VOut vMain(uint vid [[vertex_id]], uint iid [[instance_id]],
                  uint bv  [[base_vertex]], uint bi [[base_instance]],
                  device const float4* vb [[buffer(0)]]) {
    uint local_v = vid - bv;
    uint local_i = iid - bi;
    VOut o; o.pos = vb[local_v];
    o.v = float4(float(bv), float(bi), float(local_i), 1.0); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
