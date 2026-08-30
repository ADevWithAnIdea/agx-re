// r_v4vec.metal -- EXP-0168 VERTEX carrier r_v4v: FOUR float4 varyings (16
// components) across FOUR render targets, plus the device-buffer observable.
//
// THE DIMENSION.  r_v8 varies the NUMBER of slots (1 -> 8) at scalar width.
// r_v4vec varies the WIDTH of each slot at a different count: sixteen
// components carried as four vectors rather than eight scalars.  If
// `vtx_out_pos.slot`'s stride-4 corpus values (0x04/0x08/0x0c/0x10/0x14) are a
// BYTE offset into an output block rather than a slot ordinal, then the mapping
// from slot number to byte offset differs between a scalar-varying and a
// vector-varying program -- and only a carrier set containing both can tell
// those two readings apart.  That is the whole reason this carrier exists
// rather than simply adding more scalars.
//
// The sixteen values are again distinct powers of two,
//     1,2,4,8 | 16,32,64,128 | 256,512,1024,2048 | 4096,8192,16384,32768
// so any subset-sum decodes uniquely and 0.0 (lost) is unmistakable.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOut4V {
    float4 pos [[position]];
    float4 a; float4 b; float4 c; float4 d;
};

struct FOut4 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
    float4 c3 [[color(3)]];
};

vertex VOut4V v_main(uint vid [[vertex_id]],
                     constant float4 &u [[buffer(0)]],
                     device float *o [[buffer(1)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut4V r;
    r.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    r.a = u;
    r.b = u * 16.0f;
    r.c = u * 256.0f;
    r.d = u * 4096.0f;

    uint bo = vid * 32u;
    o[bo + 0] = r.pos.x; o[bo + 1] = r.pos.y; o[bo + 2] = r.pos.z; o[bo + 3] = r.pos.w;
    o[bo + 4] = r.a.x; o[bo + 5] = r.a.y; o[bo + 6] = r.a.z; o[bo + 7] = r.a.w;
    o[bo + 8] = r.b.x; o[bo + 9] = r.b.y; o[bo + 10] = r.b.z; o[bo + 11] = r.b.w;
    o[bo + 12] = r.c.x; o[bo + 13] = r.c.y; o[bo + 14] = r.c.z; o[bo + 15] = r.c.w;
    o[bo + 16] = r.d.x; o[bo + 17] = r.d.y; o[bo + 18] = r.d.z; o[bo + 19] = r.d.w;
    o[bo + 20] = float(vid);
    o[bo + 21] = -1.0f;
    o[bo + 22] = -2.0f;
    o[bo + 23] = -3.0f;
    return r;
}

fragment FOut4 f_main(VOut4V in [[stage_in]])
{
    FOut4 o;
    o.c0 = in.a; o.c1 = in.b; o.c2 = in.c; o.c3 = in.d;
    return o;
}
