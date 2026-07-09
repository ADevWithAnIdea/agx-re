// In-shader vertex fetch: index a per-vertex buffer by [[vertex_id]] and a
// per-instance buffer by [[instance_id]] (manual gl_InstanceID data path).
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float4 v; };
vertex VOut vMain(uint vid [[vertex_id]], uint iid [[instance_id]],
                  device const float4* vb [[buffer(0)]],
                  device const float4* ib [[buffer(1)]]) {
    VOut o; o.pos = vb[vid] + ib[iid];
    o.v = float4(float(vid), float(iid), 0.0, 1.0); return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
