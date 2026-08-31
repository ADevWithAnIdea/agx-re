// k_msfilt.metal -- EXP-0204 tex_sample.mode carrier A: the FILTERED-SAMPLE
// operation class.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY THIS CARRIER EXISTS.  db.json documents tex_sample.mode (op+6) as an
// OPERATION-CLASS selector with three values: 0x10 filtered sample, 0x00
// gather/read/sample_compare, 0x20 LOD query.  The dimension the field controls
// is therefore the SAMPLE-OPERATION CLASS.  Two carriers that are both, say,
// integer reads are ONE carrier for this field (EXP-0164; tex_sample.samp_extra
// read 256/256 inert on nine arms and moved on 128/256 on the tenth, the only
// one that differed in the dimension).  This experiment therefore authors one
// carrier per class and lets the compiler pick the baseline mode for each.
//
// This is the FILTERED class, and it is filtered in a way the host can predict:
// the mipmapped texture at [[texture(10)]] holds texel(x,y,L) = x + 100y +
// 10000L, and the sample coordinate is placed EXACTLY halfway between four
// level-0 texels, so a linear-filtered result is x + 100y + 50.5 while an
// unfiltered/gathered/read result cannot be.  The magnification gradient is
// 1 texel per pixel, so the implicit LOD is 0 and level 0 is the level read.
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
    constexpr sampler s(coord::normalized, filter::linear, mip_filter::linear,
                        address::clamp_to_edge);
    // pos.xy is (px + 0.5, py + 0.5); +0.5 puts the texel coordinate at
    // (px + 1.0, py + 1.0) -- the exact corner between four level-0 texels.
    float2 uv = (i.pos.xy + 0.5f) * (1.0f / 16.0f);
    float  a  = tm.sample(s, uv).x;
    return float4(a, a * 2.0f, a + 1.0f, 7.0f);
}
