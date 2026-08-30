// k_msread.metal -- EXP-0204 tex_sample.mode carrier D: the integer-READ class.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  read() has no sampler, no filter, no LOD and no derivative at all, and
// db.json places it in the same mode == 0x00 class as gather and compare.  It is
// the most constrained member of that class, and (per EXP-0172) the most
// reproducible texture carrier this corpus has.  Explicit per-level reads make
// "which level was read" directly readable from the returned value, because the
// texture content encodes its own level.
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
    uint px = uint(i.pos.x) & 7u;
    uint py = uint(i.pos.y) & 7u;
    float a = tm.read(uint2(px, py), 0).x;
    float b = tm.read(uint2(px >> 1, py >> 1), 1).x;
    float c = tm.read(uint2(px >> 2, py >> 2), 2).x;
    return float4(a, b, c, a + b + c);
}
