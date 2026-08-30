// k_ibmrt.metal -- EXP-0163 carrier for imageblock_store.b4 on MULTIPLE
// attachments.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// db.json documents byte+4 of the sibling frag_color_store as store flags,
// "0x00 in every plain store; 0x08 appears in the MRT / array-slice variant".
// imageblock_store's `b4` is the same byte offset in the same 0xe7 store family
// and is still typed `raw`.  Both EXP-0155 arms stored to a single attachment,
// so the MRT variant was never emitted.  Here the same sampling program writes
// three attachments.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; };
struct FOut {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
};

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    return o;
}

fragment FOut f_main(VO i [[stage_in]],
                     texture2d<float> t [[texture(0)]],
                     device const float *in [[buffer(0)]])
{
    constexpr sampler s(coord::normalized, filter::nearest, address::clamp_to_edge);
    float a = t.sample(s, float2(in[0], in[1])).x;
    float b = t.sample(s, float2(in[2], in[3])).x;
    float c = t.sample(s, float2(in[4], in[5])).x;
    FOut o;
    o.c0 = float4(a, b, c, in[6] * in[7]);
    o.c1 = float4(b + 5000.0f, c, a, in[8]);
    o.c2 = float4(c + 90000.0f, a, b, in[9]);
    return o;
}
