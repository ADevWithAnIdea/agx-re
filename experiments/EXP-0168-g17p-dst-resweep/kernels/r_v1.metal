// r_v1.metal -- EXP-0168 VERTEX carrier r_v1: the SINGLE-VARYING CONTROL.
//
// WHY THIS CARRIER EXISTS.  EXP-0147 swept `vtx_out_pos.dst` (16 values) and
// `vtx_out_pos.slot` (256 values) and saw 0 of 272 observations move, on ONE
// carrier whose vertex stage had exactly ONE user varying.  EXP-0164 withheld
// both fields to `untested` for that reason, and EXP-0147's own RESULTS.md sec.6
// names "vtx_out_pos.slot in a multi-varying carrier" as the open follow-up:
// `slot` selects WHICH varying/output slot, so with one varying there is
// nothing to select and the carrier is blind BY CONSTRUCTION.
//
// r_v1 reproduces that blind shape deliberately.  It is the control against
// which r_v8 / r_v8flat / r_v4vec / r_vsrc are read: if `slot` moves nothing
// here and moves something there, the EXP-0147 null is a carrier limitation and
// not a hardware don't-care.  A control that reproduces the prior null is what
// makes the positive result mean something.
//
// The varying's value is sourced from a runtime uniform (not a literal) so the
// compiler cannot fold it into an immediate, and it is IDENTICAL at all three
// vertices, so the interpolated value is exact and host-known at every covered
// pixel whatever the barycentric weights are (the EXP-0162 f_vary trick).
//
// CLEAN-ROOM: OWN-SHADER.  Every byte spliced or inspected in this experiment is
// the compiled form of this source.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOut1 {
    float4 pos [[position]];
    float4 a;
};

vertex VOut1 v_main(uint vid [[vertex_id]], constant float4 &u [[buffer(0)]])
{
    // Full-screen triangle: (-1,-1), (3,-1), (-1,3).  Covers every pixel of the
    // target, so every probe pixel is inside the primitive by construction.
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut1 o;
    o.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    o.a   = u;
    return o;
}

fragment float4 f_main(VOut1 in [[stage_in]])
{
    return in.a;
}
