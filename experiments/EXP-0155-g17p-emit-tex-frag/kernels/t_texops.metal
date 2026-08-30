// t_texops.metal -- EXP-0155 carrier T2: three DIFFERENT texture operations
// live at once (explicit-LOD sample, gather, and an unfiltered read), so the
// tex_sample `variant`/`mode`/`result_desc` sweep has adversarial replicates
// that the single-operation carrier cannot provide.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// channel 0 = sample(level(0))            -> explicit-LOD variant
// channel 1 = gather().x                  -> gather variant + result_desc
// channel 2 = read(uint2)                 -> read variant (no sampler)
// channel 3 = sentinel in[6]*in[7]        -> texture-unit-independent path
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
                       texture2d<float, access::sample> t [[texture(0)]],
                       device const float *in [[buffer(0)]])
{
    constexpr sampler s(coord::pixel, filter::nearest,
                        address::clamp_to_edge, mip_filter::none);
    float a = t.sample(s, float2(in[0], in[1]), level(0.0f)).x;
    float b = t.gather(s, float2(in[2], in[3])).x;
    float c = t.read(uint2(uint(in[4]), uint(in[5]))).x;
    float g = in[6] * in[7];
    return float4(a, b, c, g);
}
