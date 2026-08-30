// k_texread.metal -- EXP-0172 tex_sample.coord STABLE carrier: integer
// texture READ, not a filtered sample.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `tex_sample.coord` is `corpus-correlation` because its movement did not
// REPRODUCE: EXP-0155 saw it inert on three arms and live on three others (up to
// 157/256), with only 73-93% per-value cross-run agreement.  The field is a
// register index, so a swept value points the coordinate operand at whatever
// register happens to be there; on a FILTERED sample a garbage coordinate feeds
// garbage derivatives, an arbitrary LOD and an arbitrary wrap, which is exactly
// the shape of a result that does not reproduce.
//
// A `read(uint2)` has no sampler, no derivative, no LOD and no filter: a
// coordinate inside the texture returns exactly texel(x,y) = x + 100*y, and a
// coordinate outside it is bounds-checked by the texture descriptor rather than
// wrapped.  The intent is a carrier whose per-value outcome is the same on
// every run, which is what the >=99% cross-run gate needs.
//
// The preamble deliberately computes and consumes a dozen live integers before
// the reads, so that a swept register index is far more likely to land on a
// DEFINED register than on leftover state -- the other half of the
// reproducibility problem.
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
                       texture2d<float> t [[texture(0)]],
                       device const uint *b [[buffer(0)]])
{
    // Populate a wide set of live integer registers with DEFINED values.
    uint k0 = b[8],  k1 = b[9],  k2 = b[10], k3 = b[11];
    uint k4 = k0 ^ 0x11u, k5 = k1 + 2u, k6 = k2 * 3u, k7 = k3 | 4u;
    uint k8 = k4 + k5, k9 = k6 ^ k7, k10 = k8 * 5u, k11 = k9 + 6u;

    uint2 c0 = uint2(b[0], b[1]);
    uint2 c1 = uint2(b[2], b[3]);
    uint2 c2 = uint2(b[4], b[5]);
    uint2 c3 = uint2(b[6], b[7]);

    float v0 = t.read(c0).x;
    float v1 = t.read(c1).x;
    float v2 = t.read(c2).x;
    float v3 = t.read(c3).x;

    float mix = float((k0 ^ k4) + (k8 & 0xFFu) + (k10 >> 8) + (k11 & 7u));
    return float4(v0 + float(k0),
                  v1 * 2.0f + float(k5),
                  v2 * 3.0f + float(k9),
                  v3 * 5.0f + mix);
}
