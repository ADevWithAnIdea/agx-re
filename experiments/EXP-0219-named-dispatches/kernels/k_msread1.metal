// k_msread1.metal -- EXP-0219 carrier C-READ1 (AUTHORED BY US for this experiment).
// Clean-room: OWN-SHADER.
//
// WHY THIS CARRIER EXISTS.  EXP-0213 left `tex_sample.mode` NOT MET with all 53
// disagreements on `msread` and `mslodq` and every one at a value with BIT 6
// SET.  The desk step over EXP-0213's three committed quiet orders
// (analysis/desk_class_maps.txt) shows the instability is confined to
// `bit6 = 1 & bit3 = 0 & bit2 = 0`, and that with bit 6 set the OTHER mode bits
// appear to act on a DIFFERENT result slot than they do with bit 6 clear -- on
// `msread/0`, bit 1 suppresses the low 16-bit half of channel `b` when bit 6 is
// clear and of channel `c` when it is set.
//
// Every carrier that shows the effect issues THREE or FOUR adjacent texture
// instructions whose results are consumed together.  The carriers that do NOT
// show it (`msfilt`, `mscmp`, `msgath`, `msfixl`) issue one or two.  So the
// dimension to vary is THE NUMBER OF ADJACENT TEXTURE INSTRUCTIONS, and the
// extreme of that dimension is ONE.  This carrier issues exactly one `read()`
// and returns it four times, so there is no neighbouring texture result for a
// mode bit to reach.
//
// The mip texture at [[texture(10)]] holds texel(x,y,L) = x + 100y + 10000L, so
// the level actually read is directly readable off the returned value, and the
// level-1 read used here (10000..10707) cannot be confused with a level-0 read
// (0..707) or with a silent zero.
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
    float b = tm.read(uint2(px >> 1, py >> 1), 1).x;
    return float4(b, b, b, b);
}
