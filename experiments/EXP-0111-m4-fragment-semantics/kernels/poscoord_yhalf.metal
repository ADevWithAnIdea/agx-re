#include <metal_stdlib>
using namespace metal;
// FS-03: coordinate-convention (upper-left vs lower-left) probe, Y axis. A single huge
// triangle covers exactly the NDC half-plane y<0 (vertices (-10,0),(10,0),(0,-10)); the
// visible portion within the viewport is the bottom half of NDC space in a y-up NDC
// convention. Which FRAMEBUFFER ROWS (as returned by getBytes, row 0 first) get colored
// tells us whether NDC-up maps to framebuffer row 0 (upper-left/y-down window coords,
// the documented Metal convention) or to the last row (lower-left/y-up, GL-style).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-10,0), float2(10,0), float2(0,-10) };
    VOut o; o.pos = float4(p[vid], 0.0, 1.0); return o;
}
fragment float4 f_main() { return float4(1,1,1,1); }
