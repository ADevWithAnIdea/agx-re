// k_twtype.metal -- EXP-0163 texture-WRITE carrier across DATA TYPES and DATA
// SOURCES.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  db.json's tex_write note says byte+13/+14 (`data_desc`/`data_desc_hi`)
// are "0x3a/0x09 for a CONTIGUOUS vec4 register block, 0xfa/0x08 when the four
// components are ASSEMBLED FROM SCATTERED SOURCES", and that byte+2 is the
// addressing mode "sibling of the 0x67/0xe7 buffer load/store", whose own amode
// is documented as a 0x54/0x55/0x56 DATA-SOURCE mode.  EXP-0155's carrier wrote
// only contiguous float4s loaded from one buffer -- one data type, one source.
//
// Here the same program writes:
//   * a contiguous float4 loaded straight from the buffer   (texture 1)
//   * a float4 ASSEMBLED from four scattered scalars        (texture 1)
//   * a half4 into an RGBA16Float target                    (texture 8)
//   * a uint4 into an RGBA32Uint target                     (texture 9)
// so 16- and 32-bit widths, float and integer classes, and contiguous versus
// scattered data descriptors are all present at once.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; float v0; };

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.v0 = 1.0f + f;
    return o;
}

fragment float4 f_main(VO i [[stage_in]],
                       texture2d<float, access::write> w2 [[texture(1)]],
                       texture2d<half,  access::write> wh [[texture(8)]],
                       texture2d<uint,  access::write> wu [[texture(9)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[8], in[9], in[10], in[11]);          // contiguous
    float4 c1 = float4(in[19], in[12] * 2.0f, i.v0, in[16]);   // scattered
    half4  ch = half4(half(in[12]), half(in[13]), half(in[14]), half(in[15]));
    uint4  cu = uint4(uint(in[16]), uint(in[17]), uint(in[18]), uint(in[19]));
    w2.write(c0, uint2(1u, 0u));
    w2.write(c1, uint2(3u, 2u));
    wh.write(ch, uint2(5u, 4u));
    wu.write(cu, uint2(2u, 6u));
    return float4(c0.x, c1.x, float(ch.x), in[6] * in[7]);
}
