// k_msgath.metal -- EXP-0204 tex_sample.mode carrier C: the GATHER class.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  db.json puts gather in the mode == 0x00 class together with read and
// sample_compare.  A gather returns the four level-0 texels around the
// coordinate WITHOUT filtering them, so on the same texture and the same
// coordinate as carrier A its four components are x, x+1, 100+x, 101+x-shaped
// integers rather than the interpolated x + 100y + 50.5.  That is what makes
// "the operation class changed" a READABLE observation rather than merely a
// changed hash.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; };

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    return o;
}

fragment float4 f_main(VO i [[stage_in]],
                       texture2d<float> tm [[texture(10)]])
{
    constexpr sampler s(coord::normalized, filter::nearest, mip_filter::none,
                        address::clamp_to_edge);
    float2 uv = (i.pos.xy + 0.5f) * (1.0f / 16.0f);
    float4 g  = tm.gather(s, uv);
    return float4(g.x, g.y, g.z, g.w);
}
