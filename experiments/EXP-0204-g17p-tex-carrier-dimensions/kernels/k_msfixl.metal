// k_msfixl.metal -- EXP-0204 tex_sample.mode carrier B: the FILTERED-SAMPLE
// class again, but DERIVATIVE-FREE (explicit level()).  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  EXP-0172 established that implicit-LOD, derivative-dependent sampling is
// the suspected source of EXP-0155's 73-93 % cross-run instability, and that
// derivative-free texture carriers reproduce at 100 %.  Carrier A is
// implicit-LOD by construction (that is what makes it the filtered class), so
// this is its derivative-free control: the same linear magnification filter at
// the same half-texel offset, with the level named explicitly.  If A and B
// disagree across runs and B does not, the instability is the derivative, not
// the field.
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
    constexpr sampler s(coord::normalized, filter::linear, mip_filter::nearest,
                        address::clamp_to_edge);
    float2 uv = (i.pos.xy + 0.5f) * (1.0f / 16.0f);
    float  a  = tm.sample(s, uv, level(0.0f)).x;
    float  b  = tm.sample(s, uv, level(1.0f)).x;
    return float4(a, b, a + b, 7.0f);
}
