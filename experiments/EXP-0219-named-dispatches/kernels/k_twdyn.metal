// k_twdyn.metal -- EXP-0204 tex_write.amode carrier: DYNAMIC (register)
// coordinates and a raw contiguous vec4 store.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  Every tex_write ever swept -- EXP-0155's t_write and EXP-0163's twdim /
// twtype alike -- used COMPILE-TIME-CONSTANT uint2 literals for the destination
// texel.  The compiler therefore never had to form the address from a register.
// db.json's sibling enum for this byte distinguishes exactly that: "indexed
// (base+index)" versus "base-relative / GPR index".  So a dynamic, per-fragment
// coordinate is a change in the dimension amode names, and a constant one is
// not.
//
// It also separates the DATA-SOURCE half of the same enum (device_store amode
// 0x54 "ALU-computed data" vs 0x56 "direct live load-result"): one write here
// takes a contiguous float4 loaded straight out of memory with NO arithmetic
// between the load and the store, and another takes a value that has been
// through the ALU.
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; float2 uv; };

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.uv  = float2(f * 2.0f, f * 3.0f);
    return o;
}

fragment float4 f_main(VO i [[stage_in]],
                       texture2d<float, access::write>       w2 [[texture(1)]],
                       texture2d_array<float, access::write> wa [[texture(6)]],
                       device const float4 *in4 [[buffer(1)]],
                       device const float  *in  [[buffer(0)]])
{
    uint px = uint(i.pos.x) & 7u;
    uint py = uint(i.pos.y) & 7u;
    float4 draw = in4[1];                              // contiguous vec4 load
    float4 dalu = float4(in[8] + i.uv.x, in[9] * 2.0f, in[10] - 1.0f, in[11]);
    w2.write(draw, uint2(px, py));                     // dynamic coord, raw data
    w2.write(dalu, uint2(7u - px, 7u - py));           // dynamic coord, ALU data
    wa.write(draw, uint2(px, 0u), py & 3u);            // dynamic coord + slice
    return float4(draw.x, dalu.x, float(px), in[6] * in[7]);
}
