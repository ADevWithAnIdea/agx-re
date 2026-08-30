// k_texread.metal -- EXP-0172 tex_sample.coord STABLE carrier: integer texture
// READ, not a filtered sample.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  `tex_sample.coord` is `corpus-correlation` because its movement did not
// REPRODUCE: EXP-0155 saw it inert on three arms and live on three others (up to
// 157/256), with only 73-93% per-value cross-run agreement.  `coord` is op+1 of
// the 10-byte sampler op -- a REGISTER INDEX -- so a swept value points the
// coordinate operand at whatever register happens to be there.  On a FILTERED
// sample a garbage coordinate feeds garbage quad derivatives, an arbitrary LOD
// and an arbitrary wrap, which is exactly the shape of a result that does not
// reproduce.
//
// A `read(uint2)` has no sampler, no derivative, no LOD and no filter.  The
// sampled texture is R32Float with texel(x,y) = x + 100*y (harness/gfrun2.m), so
// every read NAMES its own texel and the value observed at a probe pixel says
// which coordinate the hardware actually used.  That is the value->behaviour
// partition the >=99% cross-run gate needs.
//
// NO DEVICE LOAD, NO BUFFER.  The earlier draft of this carrier took its
// coordinates from `device const uint *b [[buffer(0)]]`.  device_load on G17P is
// ASYNCHRONOUS (EXP-0169: 0..8 of 8 seed registers landed depending only on
// filler length), and against a diff-based movement oracle a load that does not
// land FABRICATES movement -- the one contamination mode that can invent a
// positive result rather than destroy one.  Coordinates are now derived from the
// interpolated [[position]] by integer ALU, so the whole program is load-free
// and every probe pixel has a host-computable expected value.
//
// The preamble deliberately computes and consumes a dozen live integers before
// the reads, so a swept register index is far more likely to land on a DEFINED
// register than on leftover state -- the other half of the reproducibility
// problem.
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
    uint px = uint(i.pos.x) & 7u;
    uint py = uint(i.pos.y) & 7u;

    // A wide set of live integer registers holding DEFINED, distinct values.
    uint k0 = px + 1u,        k1 = py + 2u;
    uint k2 = (px * 3u) & 7u, k3 = (py * 5u) & 7u;
    uint k4 = k0 ^ 0x11u,     k5 = k1 + 2u;
    uint k6 = k2 * 3u,        k7 = k3 | 4u;
    uint k8 = k4 + k5,        k9 = k6 ^ k7;
    uint k10 = k8 * 5u,       k11 = k9 + 6u;

    uint2 c0 = uint2(px, py);
    uint2 c1 = uint2(7u - px, py);
    uint2 c2 = uint2(px, 7u - py);
    uint2 c3 = uint2(k2, k3);

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
