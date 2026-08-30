// k_mslodq.metal -- EXP-0204 tex_sample.mode carrier F: the LOD-QUERY class.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY THIS IS THE CARRIER THE FIELD NEEDED.  mode == 0x20 is the LOD query, and
// NO carrier in this corpus has ever emitted one: EXP-0155 swept nine
// tex_sample fields on sample/gather/read arms only, and tex_sample.mode itself
// has never been swept at all (its label is "untested", from a two-value splice
// in RT-5).  A carrier that cannot express the LOD-query class cannot show mode
// selecting it.  Metal exposes the class directly as calculate_clamped_lod /
// calculate_unclamped_lod, and it REQUIRES a mipmapped texture -- with one level
// the clamped query is identically 0 and indistinguishable from a silent zero,
// which is why the harness gained a mipmapped sampled texture for this.
//
// The predicted values are exact and host-computed.  With normalised coordinates
// over a 16-wide texture, a coordinate of pos.xy * k has a gradient of k*16
// texels per pixel, so LOD = log2(k*16):
//     k = 1/4    -> 4 texels/pixel -> LOD 2   (also the clamp ceiling, 3 levels)
//     k = 1/8    -> 2 texels/pixel -> LOD 1
//     k = 1/32   -> 0.5 texel/pixel -> LOD -1 (clamped to 0; UNCLAMPED gives -1)
// so the clamped and unclamped forms disagree on the third, which is itself a
// control that the query really ran.
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
    constexpr sampler s(coord::normalized, filter::linear, mip_filter::linear,
                        address::clamp_to_edge);
    float l2 = tm.calculate_clamped_lod(s, i.pos.xy * 0.25f);
    float l1 = tm.calculate_clamped_lod(s, i.pos.xy * 0.125f);
    float lc = tm.calculate_clamped_lod(s, i.pos.xy * 0.03125f);
    float lu = tm.calculate_unclamped_lod(s, i.pos.xy * 0.03125f);
    return float4(l2, l1, lc, lu);
}
