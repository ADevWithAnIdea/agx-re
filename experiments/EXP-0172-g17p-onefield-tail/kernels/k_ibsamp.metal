// k_ibsamp.metal -- EXP-0163 carrier for imageblock_store.b4 (baseline shape).
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// EXP-0155's pre-freeze census found that the RGBA32Float colour output of a
// texture-sampling fragment program is encoded as `imageblock_store`, not
// `frag_color_store` -- that is where its two `ibs@*` arms came from.  This
// carrier reproduces that shape so EXP-0163 has a comparable baseline, and its
// siblings k_ibmrt / k_ibhalf then vary the ONE thing EXP-0155 held fixed: the
// number and format of the attachments the store addresses.
//
// The source texture is texel(x,y) = x + 100*y, so every sample result is an
// exact integer naming its own texel.
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
                       texture2d<float> t [[texture(0)]],
                       device const float *in [[buffer(0)]])
{
    constexpr sampler s(coord::normalized, filter::nearest, address::clamp_to_edge);
    float a = t.sample(s, float2(in[0], in[1])).x;
    float b = t.sample(s, float2(in[2], in[3])).x;
    float c = t.sample(s, float2(in[4], in[5])).x;
    return float4(a, b, c, in[6] * in[7]);   // channel 3 = ALU-only sentinel
}
