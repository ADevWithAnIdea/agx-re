// Vertex output [[clip_distance]] as a fixed-size array (user clip planes).
// Fragment is trivial: clip_distance is a vertex-only builtin and cannot appear
// in a fragment [[stage_in]], so we keep the fragment independent.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float clip [[clip_distance]] [2]; };
vertex VOut vMain(uint vid [[vertex_id]], device const float4* vb [[buffer(0)]],
                  constant float4* planes [[buffer(1)]]) {
    VOut o; o.pos = vb[vid];
    o.clip[0] = dot(vb[vid], planes[0]);
    o.clip[1] = dot(vb[vid], planes[1]);
    return o;
}
fragment float4 fMain() { return float4(1.0); }
