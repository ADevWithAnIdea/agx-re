// r_v8flat.metal -- EXP-0168 VERTEX carrier r_v8f: eight scalar varyings with
// FLAT (nointerpolation) qualifiers and NO device-buffer write.
//
// TWO DIMENSIONS AT ONCE, both deliberate:
//
//  (a) INTERPOLATION CLASS.  EXP-0163 established that a varying's
//      interpolation qualifier changes how the vertex-side store is lowered
//      (its `vflat` carrier is one of the five that moved `vary_store.hint6`).
//      If `vtx_out_pos.slot` indexes into a slot table that is partitioned by
//      interpolation class, a smooth-only carrier cannot see it.
//
//  (b) NO DEVICE WRITE.  r_v8 / r_v4vec / r_vsrc all write their outputs to a
//      device buffer, which adds `device_store` traffic to the vertex program
//      and could in principle change how the compiler assigns output slots or
//      even whether it emits `vtx_out_pos` at all.  r_v8f and r_v1 have no
//      device write, so if the buffer-writing carriers behave differently, the
//      write itself is the confound and this pair identifies it.
//
// Same eight distinct powers of two, same two-RT read-back as r_v8, and the
// values are again identical at all three vertices -- so under flat
// interpolation the observed value is exact regardless of which vertex the
// hardware treats as provoking, which is itself an unknown we do not want to
// depend on.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOut8F {
    float4 pos [[position]];
    float v0 [[flat]]; float v1 [[flat]]; float v2 [[flat]]; float v3 [[flat]];
    float v4 [[flat]]; float v5 [[flat]]; float v6 [[flat]]; float v7 [[flat]];
};

struct FOut2 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
};

vertex VOut8F v_main(uint vid [[vertex_id]], constant float4 &u [[buffer(0)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    float uu[4] = { u.x, u.y, u.z, u.w };
    VOut8F r;
    r.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    float v[8];
    for (uint k = 0; k < 8; ++k) {
        v[k] = uu[k & 3u] * ((k < 4u) ? 1.0f : 16.0f);
    }
    r.v0 = v[0]; r.v1 = v[1]; r.v2 = v[2]; r.v3 = v[3];
    r.v4 = v[4]; r.v5 = v[5]; r.v6 = v[6]; r.v7 = v[7];
    return r;
}

fragment FOut2 f_main(VOut8F in [[stage_in]])
{
    FOut2 o;
    o.c0 = float4(in.v0, in.v1, in.v2, in.v3);
    o.c1 = float4(in.v4, in.v5, in.v6, in.v7);
    return o;
}
