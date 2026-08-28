// c_kill.metal -- EXP-0143 probe for the 0x57 opcode collision flagged
// emit_unsafe in tools/agx-isa/db.json (EXP-0091, corrected by EXP-0093).
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// byte0 == 0x57 is used by BOTH the vertex-stage varying store (8 bytes) and a
// fragment-stage kill / target-mask submission op (6 bytes).  This carrier
// emits the fragment form via discard_fragment() so the two encodings can be
// compared side by side and a discriminating match derived.
//
// The discard is driven by an INTERPOLATED varying so the kill is data
// dependent and its effect is visible as a partially cleared triangle.

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

fragment float4 f_main(VOut in [[stage_in]])
{
    if (in.v0 < 2.0f) discard_fragment();
    return float4(in.v0, 7.0f, 11.0f, 13.0f);
}
