// r_rog2.metal -- EXP-0168 FRAGMENT carrier r_rog2: TWO raster order groups on
// resources of DIFFERENT TYPE, with a data dependency from one to the other.
//
// THE DIMENSION.  r_rog8 and r_rogx each order ONE resource, so an ordering
// failure can only present as "this accumulator is wrong".  r_rog2 orders two:
// an RGBA32Float texture in `raster_order_group(0)` and an RGBA32Uint texture in
// `raster_order_group(1)`, where the integer accumulator's increment is derived
// from the float accumulator's POST-update value.  Ordering failure can then
// present as an INCONSISTENCY BETWEEN THE TWO resources -- one advanced, the
// other did not, or the integer one recorded a float value that the float one
// never held.  That is a different failure signature, not a second copy of the
// same one, and it is the reason this counts as a third carrier rather than a
// third occurrence.
//
// It also puts two independent `pixel_order` brackets in one program with
// different scope, which is the closest thing available to varying the field's
// documented `scope` byte without splicing it.
//
// The integer accumulator is exact by construction: the float accumulator after
// i updates is R + i*src, and with R = src = 0.0625 the derived increment
// uint(16*(R + i*src)) is exactly i+1, so after N instances the integer texel is
// its reset plus N*(N+1)/2.  Nothing about the oracle depends on float rounding.
//
// Both resets are non-zero and are set from the command line
// (--texw-reset / --texwu-reset), so "never written" is distinguishable from
// "written with zero" in both accumulators independently of the read-back
// poison.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
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
                       texture2d<float, access::read_write> a
                           [[texture(1), raster_order_group(0)]],
                       texture2d<uint, access::read_write> b
                           [[texture(9), raster_order_group(1)]])
{
    float4 av = a.read(uint2(0, 0));
    av = av + src;
    a.write(av, uint2(0, 0));

    uint4 bv = b.read(uint2(0, 0));
    bv = bv + uint4(uint(av.x * 16.0f + 0.5f), 1u, 2u, 3u);
    b.write(bv, uint2(0, 0));

    return av + dst;
}
