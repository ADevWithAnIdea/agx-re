// k_atoff4.metal -- EXP-0163 carrier for iter_at.loc: the pull model at
// rasterSampleCount 4.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// The widest location coverage in the set: an arbitrary offset, the centroid,
// and TWO distinct explicit sample indices, all in one program at 4x, resolved.
// If `loc` selects among location rules, this is the arm where the greatest
// number of distinct rules are simultaneously live on the observed pixel.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  v0;
    float  v1;
    float  v2;
    float  v3;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0  = 3000.0f * f;
    o.v1  = 1700.0f - 900.0f * f * f;
    o.v2  = 40.0f   + 610.0f * f;
    o.v3  = 7.0f    + 1300.0f * (f * f - f);
    return o;
}

// The pull model in MSL is the metal::interpolant<> member API, not a set of
// free functions (the free-function spelling does not exist -- recorded in
// raw/prefreeze/census_run1.json as a compile failure of the first draft).
struct FIn {
    float4 pos [[position]];
    interpolant<float, interpolation::perspective> v0;
    interpolant<float, interpolation::perspective> v1;
    interpolant<float, interpolation::perspective> v2;
    interpolant<float, interpolation::no_perspective> v3;
};

fragment float4 f_main(FIn in [[stage_in]])
{
    float a = in.v0.interpolate_at_offset(float2(0.4375f, 0.3125f));
    float b = in.v1.interpolate_at_centroid();
    float c = in.v2.interpolate_at_sample(1);
    float d = in.v3.interpolate_at_sample(3);
    return float4(a, b, c, d);
}
