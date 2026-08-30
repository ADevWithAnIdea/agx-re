// k_vflat.metal -- EXP-0163 MIXED-INTERPOLATION varying carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  A [[flat]] integer varying, a no-perspective varying and an ordinary
// perspective varying are three DIFFERENT things for the varying-store side to
// describe, and EXP-0155's single vary_store carrier emitted only the third.
// If byte+2 / byte+6 / byte+7 carry an interpolation or data-type class, this is
// where they differ.  Integer varyings additionally force the flat path, which
// bypasses barycentric interpolation entirely.
//
// The geometry has all three w == 1, so perspective and no-perspective agree
// numerically; the DIFFERENCE this carrier is for is in the ENCODING, and the
// observation is still whole-attachment, so any behavioural divergence shows.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    uint   iflat  [[flat]];
    int    jflat  [[flat]];
    float  fflat  [[flat]];
    float  nopersp [[center_no_perspective]];
    float  persp;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.iflat   = 7u + uint(vid) * 3u;
    o.jflat   = -21 + int(vid) * 5;
    o.fflat   = 500.0f + 60.0f * f;
    o.nopersp = 100.0f - 3.0f * f;
    o.persp   = 1000.0f + 5.0f * f * f - 2.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(float(in.iflat) + 2.0f * float(in.jflat),
                  in.fflat, in.nopersp, in.persp);
}
