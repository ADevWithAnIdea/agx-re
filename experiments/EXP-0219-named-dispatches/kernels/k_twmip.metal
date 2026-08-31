// k_twmip.metal -- EXP-0204 tex_write.amode carrier: an EXPLICIT-LEVEL write.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY THIS CARRIER EXISTS.  tex_write.amode (byte+2) and tex_write.rsv11
// (byte+11) are the two fields the orchestrator recorded as "STILL-UNDERPOWERED:
// swept densely on 6 arms but only 2 distinct carriers with proven detection
// power (the pre-registered bar is 3)".  Those two carriers were EXP-0163's
// twdim and twtype.  What they SHARE -- and therefore what makes them one
// carrier in amode's own dimension -- is that every write in both is
//   write(colour, uint2(LITERAL, LITERAL))
// at IMPLICIT level 0, i.e. one single address form.  Both arms report
// amode == 0x54 on every occurrence.
//
// amode's dimension is named by its own sibling in the 0x67/0xe7 memory family
// (db.json device_load.addr_mode / device_store.addr_mode): 0x44 "indexed
// (base+index; terminal/standalone)", 0x54 "base-relative / non-terminal of a
// base-sharing group / GPR index", 0x56 "direct live load-result data", 0x64
// "mesh/extended".  That is an ADDRESS-FORM / OPERAND-SOURCING dimension.
//
// This carrier changes the address form: it writes to an EXPLICIT MIP LEVEL of
// a mipmapped writable texture, which adds a level operand to the address that
// no tex_write in this corpus has ever carried.  The harness reads back every
// level separately, so "wrote the wrong level" is distinguishable from "did not
// write".
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
                       texture2d<float, access::write> wm [[texture(11)]],
                       texture2d<float, access::write> w2 [[texture(1)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[ 8], in[ 9], in[10], in[11]);
    float4 c1 = float4(in[12], in[13], in[14], in[15]);
    float4 c2 = float4(in[16], in[17], in[18], in[19]);
    wm.write(c0, uint2(1u, 0u), 0u);          // explicit LEVEL 0
    wm.write(c1, uint2(1u, 1u), 1u);          // explicit LEVEL 1
    wm.write(c2, uint2(0u, 0u), 2u);          // explicit LEVEL 2
    w2.write(c0, uint2(3u, 2u));              // implicit-level control write
    return float4(c0.x, c1.x, c2.x, in[6] * in[7]);
}
