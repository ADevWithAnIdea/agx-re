// k_twbuf.metal -- EXP-0204 tex_write.amode carrier: a TEXTURE-BUFFER write.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  A texture_buffer is LINEAR one-dimensional texel storage: its write
// takes a single scalar index, not a uint2/uint3 coordinate.  It is the most
// different ADDRESS FORM the language offers for a texture write, and db.json's
// own tex_sample descriptor already recognises the buffer class as a distinct
// texture type (tex_type == 3, "buffer (linear texel buffer)").  No tex_write
// carrier in this corpus has ever written one.  If amode is an address-form
// selector, a linear-buffer destination is the case most likely to make the
// compiler choose a different value for it.
//
// A plain 2D write is kept in the same program as the within-shader control, so
// the two address forms are compared inside one compiled binary.
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
                       texture_buffer<float, access::write> tb [[texture(13)]],
                       texture2d<float, access::write>      w2 [[texture(1)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[ 8], in[ 9], in[10], in[11]);
    float4 c1 = float4(in[12], in[13], in[14], in[15]);
    float4 c2 = float4(in[16], in[17], in[18], in[19]);
    tb.write(c0, 3u);
    tb.write(c1, 17u);
    tb.write(c2, uint(i.pos.x) & 31u);        // dynamic linear index
    w2.write(c0, uint2(1u, 0u));
    return float4(c0.x, c1.x, c2.x, in[6] * in[7]);
}
