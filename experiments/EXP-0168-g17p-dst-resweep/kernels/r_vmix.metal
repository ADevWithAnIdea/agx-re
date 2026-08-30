// r_vmix.metal -- EXP-0168 VERTEX carrier r_vmix: MIXED-WIDTH varyings.
//
// THE INTERPRETIVE QUESTION THIS CARRIER EXISTS TO SETTLE.  db.json records
// `vtx_out_pos.slot` (byte+7) taking 0x04 / 0x08 / 0x0c / 0x10 / 0x14 in the
// corpus -- a STRIDE-4 sequence.  Two readings fit that equally well:
//
//   (a) `slot` is a SLOT ORDINAL scaled by 4, or
//   (b) `slot` is a BYTE OFFSET into the vertex output block.
//
// Every other carrier in this experiment has varyings of UNIFORM width -- r_v8
// and r_vsrc are eight 4-byte scalars, r_v4v is four 16-byte vectors -- and for
// uniform widths the two readings are indistinguishable, because ordinal*stride
// and byte-offset agree up to a constant factor.  They diverge only when the
// widths differ, so that the ordinal -> offset map is NON-LINEAR.  This carrier
// makes it non-linear on purpose:
//
//     half h0        2 bytes
//     half2 h1       4 bytes
//     float f0       4 bytes
//     float2 f1      8 bytes
//     float4 f2     16 bytes
//
// Sweeping `slot` densely here and comparing which slot values reach which
// observable channel therefore DISCRIMINATES between (a) and (b), which no
// amount of extra uniform-width carriers can do.  Reporting the discrimination
// -- either way, or that it is still ambiguous -- is a first-class result.
//
// The twelve observable values are again distinct powers of two
// (1,2,4,8,16,32,64,128,256,512,1024,8192) carried in three RGBA32Float render
// targets, so any subset-sum decodes uniquely and 0.0 (lost) is unmistakable.
// The half-typed values are small integers, exactly representable in binary16
// (half's significand is exact for integers up to 2048), so no oracle here
// depends on half rounding.  All values are runtime-sourced from the uniform and
// identical at all three vertices, so interpolation is exact everywhere.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOutMix {
    float4 pos [[position]];
    half   h0;
    half2  h1;
    float  f0;
    float2 f1;
    float4 f2;
};

struct FOut3 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
};

vertex VOutMix v_main(uint vid [[vertex_id]], constant float4 &u [[buffer(0)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutMix o;
    o.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    o.h0  = half(u.x);
    o.h1  = half2(u.y, u.z);
    o.f0  = u.w;
    o.f1  = float2(u.x * 16.0f, u.y * 16.0f);
    o.f2  = u * 64.0f;
    return o;
}

fragment FOut3 f_main(VOutMix in [[stage_in]])
{
    FOut3 o;
    o.c0 = float4(float(in.h0), float(in.h1.x), float(in.h1.y), in.f0);
    o.c1 = float4(in.f1.x, in.f1.y, in.f2.x, in.f2.y);
    o.c2 = float4(in.f2.z, in.f2.w, float(in.h0) * 1024.0f, in.f0 * 1024.0f);
    return o;
}
