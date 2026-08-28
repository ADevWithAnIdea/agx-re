#include <metal_stdlib>
using namespace metal;
// FS-07 compile_scan target: dfdx(v)+dfdy(v) for float4 v with algebraically independent
// components -- independent replication of the EXP-M4-13 corpus's exploratory
// derivatives_misc/deriv_vec4.metal finding (8 total 0x37/0x54 ops for a float4
// dfdx+dfdy, but with a compiler-CSE-driven 6/2 axis split there rather than an even
// 4/4 split). Hypothesis under test here: total op count == 8 (4 dfdx + 4 dfdy scalar
// ops, one per component per axis), independent of how the compiler apportions them
// between the two axes.
struct VOut { float4 pos [[position]]; float2 uv [[user(locn0)]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid],0,1); o.uv = 0.5*p[vid]+0.5; return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float4 v = float4(sin(in.uv.x*3.7), cos(in.uv.y*2.1),
                       sin(in.uv.x*1.3 + in.uv.y*5.9), cos(in.uv.x*0.7 - in.uv.y*4.4));
    return dfdx(v) + dfdy(v);
}
