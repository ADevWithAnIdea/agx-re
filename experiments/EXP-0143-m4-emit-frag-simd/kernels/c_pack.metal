// c_pack.metal -- EXP-0143 carrier for frag_color_pack / frag_color_store /
// frag_tile_setup on an 8-bit-per-channel attachment (BGRA8Unorm), where the
// compiler must emit the pack ops.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// The four varyings are chosen so that, at the probe pixel, each channel lands
// on a DISTINCT exact 8-bit unorm code, making the read-back byte an exact
// oracle with no quantization ambiguity: the per-vertex values are equal within
// a channel (so interpolation is exact and constant over the triangle) and
// differ between channels.
//   c0 = 0.2  -> 51,  c1 = 0.4 -> 102,  c2 = 0.6 -> 153,  c3 = 0.8 -> 204

#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float  c0;
    float  c1;
    float  c2;
    float  c3;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.c0 = 0.2f;
    o.c1 = 0.4f;
    o.c2 = 0.6f;
    o.c3 = 0.8f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.c0, in.c1, in.c2, in.c3);
}
