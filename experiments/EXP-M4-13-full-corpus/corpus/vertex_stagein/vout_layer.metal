// Vertex-stage layered-render outputs: [[render_target_array_index]] and
// [[viewport_array_index]] (routing from the vertex stage).
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]];
              uint layer [[render_target_array_index]];
              uint vp    [[viewport_array_index]];
              float4 v; };
vertex VOut vMain(uint vid [[vertex_id]], uint iid [[instance_id]],
                  device const float4* vb [[buffer(0)]]) {
    VOut o; o.pos = vb[vid]; o.layer = iid & 3u; o.vp = (iid >> 2) & 15u; o.v = vb[vid]; return o;
}
fragment float4 fMain(VOut in [[stage_in]]) { return in.v; }
