// k_twcomp.metal -- EXP-0204 tex_write.rsv11 carrier: ONE- and TWO-component
// write destinations.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  tex_write.rsv11 is byte+11.  Its positional sibling in the 0x67/0xe7
// memory family is device_store.st_desc_hi -- "the store data-format descriptor
// tail" -- and the neighbouring st_format_ext is documented as "bit set ONLY for
// the 3-component store".  So byte+11's dimension is the WRITE-DATA FORMAT, and
// specifically its component count.  Every destination ever swept for tex_write
// was FOUR-component: RGBA32Float (EXP-0155 t_write, EXP-0163 twdim),
// RGBA16Float and RGBA32Uint (EXP-0163 twtype).  A 4-component write is one
// carrier in this dimension however many times it is repeated.
//
// Here the same program writes an R32Float (ONE component) and an RG32Float
// (TWO components) destination alongside the RGBA32Float control, so the
// component count is an explicit, controlled variable inside one binary.
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
                       texture2d<float, access::write> wr [[texture(14)]],
                       texture2d<float, access::write> wg [[texture(15)]],
                       texture2d<float, access::write> w2 [[texture(1)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[ 8], in[ 9], in[10], in[11]);
    float4 c1 = float4(in[12], in[13], in[14], in[15]);
    float4 c2 = float4(in[16], in[17], in[18], in[19]);
    wr.write(c0, uint2(1u, 0u));              // R32Float   -> 1 component used
    wg.write(c1, uint2(3u, 2u));              // RG32Float  -> 2 components used
    w2.write(c2, uint2(5u, 4u));              // RGBA32Float control
    return float4(c0.x, c1.x, c2.x, in[6] * in[7]);
}
