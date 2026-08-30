// r_rog8.metal -- EXP-0168 FRAGMENT carrier r_rog8: the ADDITIVE ordered-RMW
// carrier for `pixel_order.kind`.
//
// WHY THIS FIELD AND THIS SHAPE.  EXP-0164 withheld `pixel_order.kind` as
// UNVERIFIABLE with reason `no-field-records`: zero per-value records anywhere
// under raw/ can be attributed to it, so the promotion cannot be reproduced from
// committed evidence.  That is an AUDITABILITY gap, not a refutation -- EXP-0162
// already established the acquire/release pair on G17P, with a quantitative
// proof of detection power.  This carrier re-records the field densely in the
// per-value JSONL schema so the claim rests on records, not on prose.
//
// THE ORDERING GUARANTEE IS THE WHOLE DESIGN.  `raster_order_group` orders
// fragments that cover THE SAME PIXEL, by primitive submission order.  It
// guarantees nothing between fragments at different pixels.  So the only
// deterministic carrier is a 1x1 render target drawn N times: N primitives, N
// fragments, one pixel, one ordered accumulator texel.  (A 16x16 target with one
// instance has 256 fragments at 256 different pixels and would measure noise --
// which is why gfrun3.m has --instances at all.)
//
// With ordering intact and accumulator reset R, source src, clear colour C,
// N instances:
//
//     texel  = R + N*src                                  (N updates, none lost)
//     pixel  = C + N*R + (N*(N+1)/2)*src
//
// A lost update moves BOTH numbers, and the gap between them says how many were
// lost.  Host-computed in harness/rendercarriers.py; nothing here consults the
// GPU to decide what the answer should be.
//
// ORDERING FAILURE LOOKS LIKE: a LOST-UPDATE COUNT.  The accumulation is
// commutative, so this carrier is blind to a pure permutation of the updates and
// sees only losses.  r_rogx and r_rog2 are the carriers that differ in exactly
// that dimension -- see their headers.
//
// CLEAN-ROOM: OWN-SHADER.  Shape re-authored from our own EXP-0147 f_rog /
// EXP-0162 render_probe.metal f_rog.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOutP { float4 pos [[position]]; };

vertex VOutP v_main(uint vid [[vertex_id]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutP o;
    o.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    return o;
}

fragment float4 f_main(float4 dst [[color(0)]],
                       constant float4 &src [[buffer(0)]],
                       texture2d<float, access::read_write> acc
                           [[texture(1), raster_order_group(0)]])
{
    float4 v = acc.read(uint2(0, 0));
    v = v + src;
    acc.write(v, uint2(0, 0));
    return v + dst;
}
