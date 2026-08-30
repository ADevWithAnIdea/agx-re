// r_vmix.metal -- EXP-0168 VERTEX carrier r_vmix: MIXED-WIDTH varyings.
//
// WHY THIS CARRIER IS THE DISCRIMINATOR, AND WHY NO NUMBER OF UNIFORM-WIDTH
// CARRIERS CAN REPLACE IT.
//
// `vtx_out_pos.slot` is claimed to select which varying/output slot the store
// targets.  Every other vertex carrier here has UNIFORM-width varyings (eight
// scalars, four float4s, ...), and for uniform widths the two candidate readings
// of `slot`
//
//     (a) an ORDINAL into a slot table, and
//     (b) a BYTE (or component) OFFSET into the vertex output block
//
// differ only by a constant factor and are therefore INDISTINGUISHABLE: every
// value of `slot` maps to the same observable under both models.  Mixing widths
// makes the ordinal -> offset map NON-LINEAR, so a dense sweep here separates
// the two readings.  That is a property of the carrier's shape, not of how many
// carriers there are -- which is rule R2 of this experiment stated positively.
//
// The twelve observables, in RT/channel order, are exactly the vector
// `rendercarriers.vtx_values_mix()` predicts:
//
//     c0 = (h0,   h1.x,  h1.y,   f0    ) = (u0,      u1,      u2,      u3     )
//     c1 = (f1.x, f1.y,  f2.x,   f2.y  ) = (u0*16,   u1*16,   u0*64,   u1*64  )
//     c2 = (f2.z, f2.w,  h0*1024, f0*1024) = (u2*64, u3*64,   u0*1024, u3*1024)
//
// Every half-typed value is a small integer and every product is a power-of-two
// multiple of one, so all twelve are EXACT in binary16 and in binary32 and the
// oracle never depends on a rounding mode.  With u = (1,2,4,8) the twelve are
// 1,2,4,8,16,32,64,128,256,512,1024,8192 -- pairwise distinct, so a redirected
// slot is DECODABLE (we learn where it went), not merely different.
//
// The attachments are RGBA32Float (MTLPixelFormat 125), so the fragment stage
// stores the interpolated values without a conversion step that could mask a
// redirect.  Values are identical at all three vertices, so the observation does
// not depend on which vertex the hardware treats as provoking -- itself an
// unknown we deliberately avoid depending on.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOutMix {
    float4 pos [[position]];
    half   h0;          // 1 component,  16-bit
    half2  h1;          // 2 components, 16-bit
    float  f0;          // 1 component,  32-bit
    float2 f1;          // 2 components, 32-bit
    float4 f2;          // 4 components, 32-bit
};

struct FOut3 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
};

vertex VOutMix v_main(uint vid [[vertex_id]], constant float4 &u [[buffer(0)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutMix r;
    r.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    r.h0 = half(u.x);
    r.h1 = half2(half(u.y), half(u.z));
    r.f0 = u.w;
    r.f1 = float2(u.x * 16.0f, u.y * 16.0f);
    r.f2 = float4(u.x * 64.0f, u.y * 64.0f, u.z * 64.0f, u.w * 64.0f);
    return r;
}

fragment FOut3 f_main(VOutMix in [[stage_in]])
{
    FOut3 o;
    o.c0 = float4(float(in.h0), float(in.h1.x), float(in.h1.y), in.f0);
    o.c1 = float4(in.f1.x, in.f1.y, in.f2.x, in.f2.y);
    o.c2 = float4(in.f2.z, in.f2.w,
                  float(in.h0) * 1024.0f, in.f0 * 1024.0f);
    return o;
}
