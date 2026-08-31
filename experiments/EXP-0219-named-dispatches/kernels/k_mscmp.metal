// k_mscmp.metal -- EXP-0204 tex_sample.mode carrier E: the DEPTH-COMPARE class.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  sample_compare is the third member of db.json's mode == 0x00 class and
// it is structurally unlike gather and read: it takes a reference value, runs a
// comparison in the sampler, and (with a linear filter) returns a FRACTION --
// the 2x2 hardware PCF that EXP-0034 validated.  Its result is confined to
// [0,1], so if splicing mode turns this occurrence into a plain filtered sample
// or an LOD query the returned value leaves [0,1] and the change is readable,
// not merely a changed hash.
//
// The depth texture at [[texture(5)]] holds depth(x,y) = (x + 8y)/64.
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
                       depth2d<float> td [[texture(5)]])
{
    // coord::pixel forbids a compare_func in a Metal sampler, so the compare
    // samplers are normalised; the 8x8 depth texture holds depth(x,y)=(x+8y)/64
    // and the coordinate is placed on the corner between four texels, which is
    // where a LINEAR compare sampler produces a genuine 2x2 PCF FRACTION.
    constexpr sampler sc(coord::normalized, filter::linear,
                         address::clamp_to_edge, compare_func::less);
    constexpr sampler sn(coord::normalized, filter::nearest,
                         address::clamp_to_edge, compare_func::greater_equal);
    float2 p = (float2(float(uint(i.pos.x) & 7u), float(uint(i.pos.y) & 7u))
                + 1.0f) * (1.0f / 8.0f);
    float  r = 0.25f;
    float  a = td.sample_compare(sc, p, r);
    float  b = td.sample_compare(sn, p, r);
    return float4(a, b, a * 4.0f + b, 7.0f);
}
