// r_v8.metal -- EXP-0168 VERTEX carrier r_v8: EIGHT scalar varyings + a DIRECT
// per-vertex device-buffer observable.
//
// THE DIMENSION UNDER TEST.  `vtx_out_pos.slot` (byte+7) is documented in
// db.json as the "varying/output slot" and is observed in the corpus taking
// 0x04/0x08/0x0c/0x10/0x14 -- a stride-4 index.  The dimension it selects is
// therefore THE NUMBER AND IDENTITY OF OUTPUT SLOTS.  EXP-0147's carrier had one
// user varying; this one has eight, each carrying a DISTINCT POWER OF TWO:
//
//     v0..v7 = (1, 2, 4, 8, 16, 32, 64, 128)
//
// Powers of two are chosen so the observation is not merely "different" but
// DECODABLE: any subset-sum of the eight is unique, so a read-back channel says
// exactly which slot(s) reached it -- swapped, duplicated, merged or lost -- and
// 0.0 (lost) is distinguishable from every legal value.  The eight land in two
// RGBA32Float render targets, four channels each, so all eight are read back
// individually.
//
// THE SECOND, INDEPENDENT OBSERVATION PATH.  EXP-0163's harness already binds
// the `--out-buf` device buffer to the VERTEX stage (`setVertexBuffer:`) but no
// carrier it built ever used it.  Here the vertex stage writes its own outputs
// to that buffer as well as emitting them as varyings.  That gives
// `vtx_out_pos` a DIRECT per-vertex observable that does not pass through
// rasterization or interpolation at all, alongside the interpolated pixel:
//
//   * buffer  -> "the vertex stage ran and computed value X for vertex n"
//   * pixel   -> "value X was routed to output slot k"
//
// A field that changes the routing moves the pixel and leaves the buffer alone;
// a field that changes the computation moves both; a program that never ran
// leaves the buffer at its 0xDEADBEEF poison.  Those three are otherwise
// indistinguishable, which is exactly the failure mode FIELD-SWEEP-PROTOCOL
// sec.7 was written about.
//
// Buffer layout: 32 floats per vertex (stride fixed across every EXP-0168
// vertex carrier).  Slots 16..31 are written by NOTHING, so they are a TAIL
// POISON REGION: if a dispatch reports OK and the tail is no longer poison,
// something wrote out of bounds.
//
// Values are sourced from a runtime uniform so they cannot be constant-folded,
// and are identical at all three vertices so the interpolated value is exact at
// every covered pixel.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOut8 {
    float4 pos [[position]];
    float v0; float v1; float v2; float v3;
    float v4; float v5; float v6; float v7;
};

struct FOut2 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
};

vertex VOut8 v_main(uint vid [[vertex_id]],
                    constant float4 &u [[buffer(0)]],
                    device float *o [[buffer(1)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    float uu[4] = { u.x, u.y, u.z, u.w };
    float v[8];
    for (uint k = 0; k < 8; ++k) {
        v[k] = uu[k & 3u] * ((k < 4u) ? 1.0f : 16.0f);
    }

    VOut8 r;
    r.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    r.v0 = v[0]; r.v1 = v[1]; r.v2 = v[2]; r.v3 = v[3];
    r.v4 = v[4]; r.v5 = v[5]; r.v6 = v[6]; r.v7 = v[7];

    uint b = vid * 32u;
    o[b + 0] = r.pos.x; o[b + 1] = r.pos.y; o[b + 2] = r.pos.z; o[b + 3] = r.pos.w;
    for (uint k = 0; k < 8; ++k) {
        o[b + 4u + k] = v[k];
    }
    // Fixed markers: present iff the vertex stage ran, and independent of every
    // value under test.
    o[b + 12] = float(vid);
    o[b + 13] = -1.0f;
    o[b + 14] = -2.0f;
    o[b + 15] = -3.0f;
    return r;
}

fragment FOut2 f_main(VOut8 in [[stage_in]])
{
    FOut2 o;
    o.c0 = float4(in.v0, in.v1, in.v2, in.v3);
    o.c1 = float4(in.v4, in.v5, in.v6, in.v7);
    return o;
}
