// t_coord.metal -- EXP-0155 carrier T4: sampling texture classes that need MORE
// THAN TWO coordinate components, to provoke the coordinate-setup op
// (tex_coord_setup) that the plain 2D carrier does not emit.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// The pre-freeze census showed t_sample/t_texops emit tex_sample with NO
// tex_coord_setup at all: a float2 coordinate needs no packing step.  A 3D
// sample, a cube sample and a 2D-array sample each carry a third component, so
// this carrier is the one that can host the tex_coord_setup arms.
//
// channel 0 = texture3d   sample
// channel 1 = texturecube sample
// channel 2 = texture2d_array sample
// channel 3 = sentinel in[6]*in[7] (plain ALU, texture-unit-independent)
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
                       texture3d<float, access::sample> t3 [[texture(2)]],
                       texturecube<float, access::sample> tc [[texture(3)]],
                       texture2d_array<float, access::sample> ta [[texture(4)]],
                       device const float *in [[buffer(0)]])
{
    constexpr sampler s(coord::normalized, filter::nearest,
                        address::clamp_to_edge, mip_filter::none);
    float a = t3.sample(s, float3(in[0], in[1], in[2])).x;
    float b = tc.sample(s, float3(in[2], in[3], in[4])).x;
    float c = ta.sample(s, float2(in[4], in[5]), uint(in[0])).x;
    float g = in[6] * in[7];
    return float4(a, b, c, g);
}
