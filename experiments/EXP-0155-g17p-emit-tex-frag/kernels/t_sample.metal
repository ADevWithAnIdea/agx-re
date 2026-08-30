// t_sample.metal -- EXP-0155 carrier T1: THREE independent implicit-LOD texture
// samples in the FRAGMENT stage, each landing in its own colour channel.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY FRAGMENT AND NOT COMPUTE.  EXP-0142 swept tex_sample from a compute
// carrier and never obtained a baseline.  More importantly the dispatch's
// liveness rule (EXP-0129's loss) asks for the value to reach the OBSERVED
// PIXEL, and the implicit-LOD sample form only exists in a fragment program.
//
// TEXTURE.  gfrun binds an R32Float 8x8 texture at fragment [[texture(0)]] with
// texel(x,y) = x + 100*y, so every sample result is an exact integer that names
// the texel it came from.  A coordinate change, a result-register change and a
// silent zero are therefore three DIFFERENT read-back floats, not three ways of
// getting "something wrong".
//
// LIVENESS.  sample j's result reaches colour channel j and nothing else does.
// Channel 3 is the INTEGRITY SENTINEL: in[6]*in[7], computed on the plain float
// ALU, never touching the texture unit.  Channel 3 therefore reports
// independently whether the dispatch as a whole ran, so a dead texture unit is
// distinguishable from a dead shader (FIELD-SWEEP-PROTOCOL sec.7).
//
// Coordinates come from buffer(0) (uniform across the primitive) so the
// implicit LOD is exactly 0 and the host oracle is exact.
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
    float a = t.sample(s, float2(in[0], in[1])).x;
    float b = t.sample(s, float2(in[2], in[3])).x;
    float c = t.sample(s, float2(in[4], in[5])).x;
    float g = in[6] * in[7];      // sentinel: plain ALU, texture-unit-independent
    return float4(a, b, c, g);
}
