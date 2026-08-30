// r_rogx.metal -- EXP-0168 FRAGMENT carrier r_rogx: the NON-COMMUTATIVE ordered
// -RMW carrier for `pixel_order.kind`.
//
// THE DIMENSION THIS CARRIER DIFFERS IN, and it is the one the field controls.
// `pixel_order.kind` selects acquire/wait versus release/signal -- i.e. WHICH
// HALF of an ordering bracket an instruction is.  A carrier can only speak to
// that if ordering failure LOOKS DIFFERENT in it.  r_rog8 accumulates with `+`,
// which is commutative: it detects lost updates and is blind to a pure
// reordering of surviving ones.  r_rogx accumulates with an AFFINE recurrence
//
//     v <- v * 2 + src
//
// which is NOT permutation-invariant and not idempotent.  After k applications
// from reset R the texel is exactly
//
//     v_k = 2^k * R + (2^k - 1) * src
//
// so every distinct number of applications lands on its own value, and the
// accumulated pixel
//
//     pixel = C + sum_{i=1..N} v_i = C + (2^(N+1) - 2)*R + (2^(N+1) - 2 - N)*src
//
// is a second, independent count of the same events.  With R and src chosen
// dyadic every one of those is exact in binary32, so the host oracle enumerates
// the whole family and names the observation rather than merely calling it
// "different".
//
// The accumulator reset is deliberately NON-ZERO here (r_rog8 uses zero to
// replicate EXP-0162 exactly), so "the shader wrote 0" and "the shader never
// wrote" stay distinguishable in this carrier even before the poison rule is
// applied.
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
                       texture2d<float, access::read_write> acc
                           [[texture(1), raster_order_group(0)]])
{
    float4 v = acc.read(uint2(0, 0));
    v = v * 2.0f + src;
    acc.write(v, uint2(0, 0));
    return v + dst;
}
