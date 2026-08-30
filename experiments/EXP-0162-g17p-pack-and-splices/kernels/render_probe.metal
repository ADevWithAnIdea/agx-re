// EXP-0162 render-stage carriers -- OUR OWN MSL.
//
// R-ROG  : the raster-order-group carrier (EXP-0147's f_rog shape, re-authored
//          here so this experiment is self-contained). A TEXTURE-tagged
//          raster_order_group compiles to the `pixel_order` acquire/release
//          pair. Every instance covers texel (0,0), so N instances perform N
//          read-modify-writes the pair must serialise:
//              tex_after = N * src            (N updates, none lost)
//              pixel     = clear + sum(1..N) * src
//          A lost update shows up in BOTH numbers, and the difference between
//          them tells how many were lost.
//
// R-KILL : the fragment sample-kill carrier (EXP-0091's s_kill_probe shape,
//          re-authored with a float-sourced mask so the existing render runner's
//          float4 fragment buffer can drive it). Compiles to the 6-byte
//          byte0=0x57 fragment submission op that `vary_store` currently
//          mis-tokenizes as an 8-byte vertex-stage varying store.
//              mask bit0 set   -> fragment survives -> colour = (0.75,0.5,0.25,1)
//              mask == 0       -> fragment killed   -> colour = clear
//
// R-VARY : an ordinary vertex-stage varying carrier: four user varyings plus
//          [[position]], i.e. the genuine 8-byte `vary_store` form, so the same
//          length hypothesis can be falsified from the OTHER side.
//
// CLEAN-ROOM: OWN-SHADER. Every byte inspected or spliced is the compiled form
// of this file. No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------- R-ROG
struct VOutP { float4 pos [[position]]; };
vertex VOutP v_rog(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutP o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_rog(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]],
                      texture2d<float, access::read_write> acc
                          [[texture(0), raster_order_group(0)]]) {
    float4 v = acc.read(uint2(0, 0));
    v = v + src;
    acc.write(v, uint2(0, 0));
    return v + dst;
}

// ---------------------------------------------------------------- R-KILL
struct FOutK { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
vertex VOutP v_kill(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutP o; o.pos = float4(p * 2.0 - 1.0, 0.1, 1.0); return o;
}
fragment FOutK f_kill(constant float4 &want [[buffer(0)]]) {
    FOutK o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);
    o.mask = uint(want.x);          // runtime-sourced: not const-folded
    return o;
}

// ---------------------------------------------------------------- R-VARY
struct VOutV {
    float4 pos [[position]];
    float4 va;
};
vertex VOutV v_vary(uint vid [[vertex_id]], constant float4 &u [[buffer(0)]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutV o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.va  = float4(u.x + float(vid), u.y, u.z, u.w);
    return o;
}
fragment float4 f_vary(VOutV in [[stage_in]]) { return in.va; }
