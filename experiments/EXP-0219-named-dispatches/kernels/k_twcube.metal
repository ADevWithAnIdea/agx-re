// k_twcube.metal -- EXP-0204 tex_write.amode carrier: a CUBE-FACE write.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  db.json documents tex_write.coord_dim == 0x0c as "cube", and states that
// byte+4 carries the extra coordinate (array layer / CUBE FACE).  EXP-0163
// deliberately widened the destination dimensionality to 2D-array and 3D but
// NEVER emitted a cube write, so the one coord_dim code the descriptor names and
// nothing has ever produced is still unexercised.  A cube write addresses a face
// as well as a texel, which is again an ADDRESS-FORM change.
//
// The harness resets and reads back all six faces separately, so writing the
// wrong face is distinguishable from not writing.
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
                       texturecube<float, access::write> wc [[texture(12)]],
                       texture2d<float, access::write>   w2 [[texture(1)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[ 8], in[ 9], in[10], in[11]);
    float4 c1 = float4(in[12], in[13], in[14], in[15]);
    float4 c2 = float4(in[16], in[17], in[18], in[19]);
    wc.write(c0, uint2(1u, 0u), 0u);          // face 0
    wc.write(c1, uint2(3u, 2u), 4u);          // face 4  (non-zero face)
    wc.write(c2, uint2(5u, 4u), uint(i.pos.x) % 6u);   // dynamic face
    w2.write(c0, uint2(7u, 6u));
    return float4(c0.x, c1.x, c2.x, in[6] * in[7]);
}
