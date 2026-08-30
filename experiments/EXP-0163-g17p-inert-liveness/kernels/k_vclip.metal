// k_vclip.metal -- EXP-0163 CLIP-DISTANCE carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  [[clip_distance]] is a vertex output that is NOT a user varying and NOT
// [[position]]: it is consumed by fixed-function clipping.  If the varying-store
// encoding distinguishes classes of destination -- position vs user varying vs
// system output -- this is a class EXP-0155's carrier never produced.  It is
// also a Vulkan/GL-facing capability worth bounding on its own
// (CLAUDE.md "Metal-subset heuristic").
//
// One clip distance is positive over most of the triangle and negative in a
// corner, so the clip is BEHAVIOURALLY live: a lost or corrupted clip-distance
// store changes which pixels are shaded at all.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  clip [[clip_distance]] [1];
    float  v0;
    float  v1;
    float  v2;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.clip[0] = 1.0f - 1.5f * f;      // +1, -0.5, -2 : clips part of the triangle
    o.v0  = 1.0f    + f;
    o.v1  = 10.0f   + f * f;
    o.v2  = 100.0f  - 3.0f * f;
    return o;
}

// A [[clip_distance]] member cannot appear in a stage_in struct, so the
// fragment stage takes its OWN input struct without it (recorded as a compile
// failure of the first draft in raw/prefreeze/census_run1.json).
struct FIn {
    float4 pos [[position]];
    float  v0;
    float  v1;
    float  v2;
};

fragment float4 f_main(FIn in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, 42.0f);
}
