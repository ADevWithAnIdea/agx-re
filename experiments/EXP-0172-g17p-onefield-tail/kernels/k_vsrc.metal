// k_vsrc.metal -- EXP-0163 VARYING-DATA-SOURCE carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  db.json's vary_store note says byte+2 (hint2) "carries the same
// 0x54/0x55/0x56 data-source mode as the device_store amode".  A data-source
// mode can only differ if the data comes from different sources.  EXP-0155's
// single carrier computed all four varyings arithmetically in registers, i.e.
// ONE source.  Here half the varyings are forwarded straight out of a bound
// uniform buffer, one is a compile-time constant, and the rest are computed --
// three distinct provenances in one vertex program.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  fromBuf0;
    float  fromBuf1;
    float  konst;
    float  computed;
};

vertex VOut v_main(uint vid [[vertex_id]],
                   const device float *u [[buffer(0)]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.fromBuf0 = u[vid];             // straight out of memory, no ALU
    o.fromBuf1 = u[vid + 3u];
    o.konst    = 777.0f;             // an immediate
    o.computed = 1000.0f + 5.0f * f * f - 2.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.fromBuf0, in.fromBuf1, in.konst, in.computed);
}
