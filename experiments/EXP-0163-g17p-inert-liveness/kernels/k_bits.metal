// k_bits.metal -- EXP-0163 BITFIELD carrier for the same polymorphic 0x2f op.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// db.json enumerates `tex_coord_setup.form` value 16 as "bitfield/shift-prep",
// a form no EXP-0155 carrier emitted.  extract_bits / insert_bits / rotate /
// clz / popcount / reverse_bits are the MSL entry points that need exactly that
// preparation, and each result here is an exact integer the host can compute.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 1.0f + f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]],
                       const device uint *u [[buffer(0)]])
{
    uint x = u[0] ^ uint(in.v0);
    uint y = u[1];
    uint e = extract_bits(x, 5, 11);
    uint i = insert_bits(x, y, 9, 7);
    uint r = rotate(x, 13u);
    uint p = popcount(x) + (clz(y) << 8) + (reverse_bits(x) >> 16);
    return float4(float(e), float(i & 0xFFFFFu), float(r & 0xFFFFFu), float(p));
}
