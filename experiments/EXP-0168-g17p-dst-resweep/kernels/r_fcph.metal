// r_fcph.metal -- EXP-0168 FRAGMENT carrier r_fcph for `frag_color_pack.dst`:
// the 16-BIT FLOAT attachment shape.
//
// THE DIMENSION.  r_fcp1 and r_fcp4 both target an 8-bit UNORM attachment, so
// both exercise the same conversion class -- float -> 8-bit normalised integer,
// two components per packed 32-bit word.  RGBA16Float is a different conversion
// class: no normalisation, two 16-bit floats per word.  If the pack's
// destination-register assignment is a function of how many components share a
// word or of the conversion the pack performs, an 8-bit-only carrier set cannot
// see it.  This is the third genuinely distinct attachment class available
// without leaving formats the harness already reads back correctly
// (bytesPerPixel(115) == 8).
//
// The four values are exactly representable in binary16 (1.5, 3.25, 7.125,
// 15.0625 -- all within half's precision at their exponents), so the read-back
// half bit patterns are an exact oracle with no rounding ambiguity, and they are
// runtime-sourced so they cannot be folded into the pack immediate.  Values are
// equal at all three vertices, so interpolation is exact.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOutC4 {
    float4 pos [[position]];
    float c0; float c1; float c2; float c3;
};

vertex VOutC4 v_main(uint vid [[vertex_id]], constant float4 &u [[buffer(0)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutC4 o;
    o.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    o.c0 = u.x;
    o.c1 = u.y;
    o.c2 = u.z;
    o.c3 = u.w;
    return o;
}

fragment float4 f_main(VOutC4 in [[stage_in]])
{
    return float4(in.c0, in.c1, in.c2, in.c3);
}
