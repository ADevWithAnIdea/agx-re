#include <metal_stdlib>
using namespace metal;
// FS-03 companion: same technique, X axis. Triangle covers exactly NDC x<0
// (vertices (0,-10),(0,10),(-10,0)) -- confirms left/right framebuffer-column mapping
// (uncontested, included for completeness/symmetry with the Y-axis probe).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(0,-10), float2(0,10), float2(-10,0) };
    VOut o; o.pos = float4(p[vid], 0.0, 1.0); return o;
}
fragment float4 f_main() { return float4(1,1,1,1); }
