#include <metal_stdlib>
using namespace metal;
// FS-01 HW-splice target (corner geometry): a single right triangle covers EXACTLY
// pixel column2/row1 of a 3x2 target (edges at NDC x=1/3 and NDC y=0, verified in pilot
// analysis) -- so exactly ONE fragment invocation ever runs, at a KNOWN asymmetric
// position (px=2,py=1 -> pos=(2.5,1.5)), and it writes to FIXED buffer slots (no
// position-derived addressing), so a get_sr splice changes only the STORED VALUE, never
// the write address (avoiding the compound addressing/value effect of poscoord_grid).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(1.0/3.0, 0.0), float2(10.0, 0.0), float2(1.0/3.0, -10.0) };
    VOut o; o.pos = float4(p[vid], 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]], device uint *buf [[buffer(0)]]) {
    buf[0] = as_type<uint>(pos.x);
    buf[1] = as_type<uint>(pos.y);
    return float4(0,0,0,1);
}
