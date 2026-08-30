// r_vsrc.metal -- EXP-0168 VERTEX carrier r_vsrc: eight scalar varyings whose
// values come from a SERIAL DEPENDENCY CHAIN, not from four uniform lanes.
//
// THE DIMENSION, and it is the one `vtx_out_pos.dst` needs.  db.json models
// byte0's high nibble as `dst`, a 4-bit REGISTER selector; whatever its exact
// role (destination, or the source register whose value is emitted), the only
// dimension a register index can control is WHICH REGISTER FEEDS THE OUTPUT.
// r_v8 sources its eight varyings from four uniform lanes, so the compiler is
// free to reuse a small register set.  r_vsrc forces eight DISTINCT live values
// produced in sequence, each depending on the last:
//
//     t0 = u.x                       = 1
//     t(k+1) = t(k) * 1.5 + u.y      -> 3.5, 7.25, 12.875, 21.3125,
//                                       33.96875, 52.953125, 81.4296875
//
// Every intermediate is a dyadic rational exactly representable in binary32, so
// the host oracle is exact whether or not the compiler contracts the multiply
// and add into an FMA.  Eight simultaneously live, mutually distinct values is
// the register-space condition EXP-0138's `copysign.operands` sweep lacked --
// it read inert because its carrier had only TWO live float registers, so a
// register-selector field had nothing to select between.  This carrier is that
// lesson applied to the vertex stage.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOut8S {
    float4 pos [[position]];
    float v0; float v1; float v2; float v3;
    float v4; float v5; float v6; float v7;
};

struct FOut2 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
};

vertex VOut8S v_main(uint vid [[vertex_id]],
                     constant float4 &u [[buffer(0)]],
                     device float *o [[buffer(1)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    float v[8];
    v[0] = u.x;
    for (uint k = 1; k < 8; ++k) {
        v[k] = v[k - 1] * 1.5f + u.y;
    }
    VOut8S r;
    r.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    r.v0 = v[0]; r.v1 = v[1]; r.v2 = v[2]; r.v3 = v[3];
    r.v4 = v[4]; r.v5 = v[5]; r.v6 = v[6]; r.v7 = v[7];

    uint b = vid * 32u;
    o[b + 0] = r.pos.x; o[b + 1] = r.pos.y; o[b + 2] = r.pos.z; o[b + 3] = r.pos.w;
    for (uint k = 0; k < 8; ++k) {
        o[b + 4u + k] = v[k];
    }
    o[b + 12] = float(vid);
    o[b + 13] = -1.0f;
    o[b + 14] = -2.0f;
    o[b + 15] = -3.0f;
    return r;
}

fragment FOut2 f_main(VOut8S in [[stage_in]])
{
    FOut2 o;
    o.c0 = float4(in.v0, in.v1, in.v2, in.v3);
    o.c1 = float4(in.v4, in.v5, in.v6, in.v7);
    return o;
}
