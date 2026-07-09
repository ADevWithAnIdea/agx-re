// Kitchen-sink vertex special outputs together: position + point_size +
// clip_distance[4] + render_target_array_index. Trivial fragment (clip is
// vertex-only). Compiled with --topology 3.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float ps [[point_size]];
              float clip [[clip_distance]] [4]; uint layer [[render_target_array_index]]; };
vertex VOut vMain(uint vid [[vertex_id]], uint iid [[instance_id]],
                  device const float4* vb [[buffer(0)]]) {
    VOut o; o.pos = vb[vid]; o.ps = clamp(vb[vid].w, 1.0, 32.0);
    o.clip[0]=vb[vid].x; o.clip[1]=-vb[vid].x; o.clip[2]=vb[vid].y; o.clip[3]=1.0-vb[vid].z;
    o.layer = iid & 7u; return o;
}
fragment float4 fMain() { return float4(1.0); }
