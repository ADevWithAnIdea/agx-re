#include <metal_stdlib>
using namespace metal;
// FS-07 compile_scan target: dfdx() applied to a float value. Counts how many 10-byte
// 0x37/byte+2==0x54 derivative ops appear -- hypothesis (scalarize_ddx=true) predicts
// exactly 1, axis=dfdx (0x92) only.
struct VOut { float4 pos [[position]]; float2 uv [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float v = sin(in.uv.x*3.7);
    float d = dfdx(v);
    return float4(d, 0.0, 0.0, 1.0);
}
