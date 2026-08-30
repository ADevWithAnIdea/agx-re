// t_lodoff.metal -- EXP-0155 carrier T6: the sample forms whose COORDINATE /
// LOD / gather-offset operands must be computed by a setup op --
// a const-offset gather, a biased sample, a gradient sample and a depth
// compare.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  The pre-freeze census showed that neither a plain float2 sample nor a
// 3D/cube/array sample emits `tex_coord_setup` (byte0 low-nibble 0xb with
// byte+2 == 0x2f); they emit the sibling 0x27 form the DB calls b_alu10_lo7.
// db.json attributes tex_coord_setup to exactly these four shapes (EXP-0037's
// k_tex_gather / k_tex_lod / k_tex_compare / k_tex_array_cube), so this carrier
// is the pre-registered attempt to host the tex_coord_setup arms.  If it still
// does not emit the op, that is recorded as a NEGATIVE result and the
// instruction's fields stay `untested`.
//
// channel 0 = gather with a constant per-axis offset
// channel 1 = sample with an LOD BIAS
// channel 2 = sample with explicit GRADIENTS
// channel 3 = depth-compare result + the ALU sentinel
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
                       depth2d<float, access::sample> d [[texture(5)]],
                       device const float *in [[buffer(0)]])
{
    constexpr sampler s(coord::pixel, filter::nearest,
                        address::clamp_to_edge, mip_filter::none);
    constexpr sampler sc(coord::normalized, filter::linear,
                         address::clamp_to_edge, mip_filter::none,
                         compare_func::less);
    float a = t.gather(s, float2(in[0], in[1]), int2(1, -1)).x;
    float b = t.sample(s, float2(in[2], in[3]), bias(in[6])).x;
    float c = t.sample(s, float2(in[4], in[5]),
                       gradient2d(float2(in[6], 0.0f), float2(0.0f, in[7]))).x;
    float e = d.sample_compare(sc, float2(in[0], in[1]), in[7]);
    return float4(a, b, c, e + in[6] * in[7]);
}
