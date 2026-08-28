#include <metal_stdlib>
using namespace metal;
// FS-01 compile_scan target: minimal fragment reading [[position]].xy and writing the
// raw values out, nothing else, so the only get_sr traffic in the fragment main is the
// position read (isolates the get_sr 0xa0/0xa1 + int->float+0.5 conversion sequence for
// byte-level inspection).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]]) {
    return float4(pos.x, pos.y, 0.0, 1.0);
}
