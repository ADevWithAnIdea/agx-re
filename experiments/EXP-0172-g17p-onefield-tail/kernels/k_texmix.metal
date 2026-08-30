// k_texmix.metal -- EXP-0172 tex_sample.coord carrier B: the SAME descriptor
// reached through three different operation kinds in one program -- an
// explicit-LOD sample, a gather, and an integer read -- so that a `coord`
// verdict is not a property of one operation kind.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  db.json models `tex_sample` as one bundle covering sample / gather /
// read / compare / LOD-query, with `variant` (op+2) selecting which.  `coord`
// (op+1) is the coordinate register in all of them.  EXP-0155's live and inert
// arms were not separated by operation kind and its cross-run disagreement was
// never attributed.  This carrier makes the operation kind an explicit,
// controlled variable inside one compiled program.
//
// Every operation is explicit-LOD or LOD-free, so no result here depends on a
// quad derivative -- the suspected source of EXP-0155's irreproducibility -- and
// (as in k_texread.metal) there is NO buffer and NO device_load, so nothing
// depends on an asynchronous load landing (EXP-0169).
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
                       texture2d<float> t [[texture(0)]])
{
    constexpr sampler s(coord::pixel, filter::nearest, address::clamp_to_edge);

    uint px = uint(i.pos.x) & 7u;
    uint py = uint(i.pos.y) & 7u;

    float2 p0 = float2(float(px) + 0.5f, float(py) + 0.5f);
    float2 p1 = float2(float(7u - px) + 0.5f, float(py) + 0.5f);
    uint2  c2 = uint2(px, 7u - py);
    uint2  c3 = uint2((px * 3u) & 7u, (py * 5u) & 7u);

    float  a = t.sample(s, p0, level(0)).x;
    float4 g = t.gather(s, p1);
    float  r = t.read(c2).x;
    float  q = t.read(c3, 0).x;

    return float4(a,
                  g.x + 2.0f * g.y + 3.0f * g.z + 5.0f * g.w,
                  r * 7.0f,
                  q * 11.0f + a);
}
