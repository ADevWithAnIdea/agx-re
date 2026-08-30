// EXP-0147 render-stage carriers -- OWN-SHADER MSL, authored fresh for this
// experiment. Each function exists to place ONE pipeline-plumbing instruction
// (tile_read / tile_read_mrt / vtx_out_pos / vtx_coord_xform / pixel_order /
// n3_sample_read) on a path whose result is observable in a read-back pixel or
// read-back texel, so a field splice inside that instruction is falsifiable.
//
// CLEAN-ROOM: every byte we splice is the compiled form of the source below,
// compiled by the public newLibraryWithSource: API. No Apple binary is
// disassembled, decompiled, or introspected.

#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------- vertex ----

// V-ARRAY: full-screen triangle from an indexed constant array + a uniform.
// This shape compiles to a vertex program containing `vtx_coord_xform`
// (byte0 0x17, byte+2 0xa2, byte+3 0xb0).
struct VOutC { float4 pos [[position]]; float4 vc; };
vertex VOutC v_arr(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    VOutC o;
    o.pos = float4(p[vid], 0.0, 1.0);
    o.vc  = vp * float(vid + 1);
    return o;
}

// V-TERNARY: the same full-screen triangle built from ternaries instead of an
// indexed array. This shape compiles to a vertex program containing
// `vtx_out_pos` (low-nibble-0xb leader, `0b 00 26 00 40 00 00 SS`).
static float2 tri(uint vid) { return float2((vid == 2) ? 3.0 : -1.0, (vid == 1) ? 3.0 : -1.0); }
struct VOutA { float4 pos [[position]]; float4 va; };
vertex VOutA v_tern(uint vid [[vertex_id]]) {
    VOutA o;
    o.pos = float4(tri(vid), 0.0, 1.0);
    o.va  = float4(vid == 0 ? 0.90 : 0.10,
                   vid == 1 ? 0.90 : 0.10,
                   vid == 2 ? 0.90 : 0.10, 1.0);
    return o;
}

// V-SAMPLE: vertex half of the per-sample-interpolation carrier.
struct VOutS { float4 pos [[position]]; float4 a [[sample_perspective]]; };
vertex VOutS v_samp(uint vid [[vertex_id]]) {
    VOutS o;
    o.pos = float4(tri(vid), 0.0, 1.0);
    o.a   = float4(vid == 0 ? 0.90 : 0.10,
                   vid == 1 ? 0.75 : 0.20,
                   vid == 2 ? 0.60 : 0.30, 1.0);
    return o;
}

// -------------------------------------------------------------- fragment ----

// F-TILE: the tile_read carrier. `[[color(0)]]` reads the tile's resident value
// (established by MTLLoadActionClear with an exact float clear colour) and the
// genuinely non-foldable ALU (`dst*2 + src`, src a runtime uniform) stops the
// compiler eliding the read the way EXP-0130/EXP-0117 saw for a pure
// passthrough. Compiles to `tile_read` (67 0e 54) + `frag_color_store`.
fragment float4 f_tile(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]]) {
    return dst * 2.0 + src;
}

// F-MRT: two colour attachments, both read and both written, each with a
// DIFFERENT combine so a mis-routed render-target index is visible. Compiles to
// the `tile_read_mrt` (67 06 54) plain-read variant.
struct MRTOut { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment MRTOut f_mrt(float4 d0 [[color(0)]], float4 d1 [[color(1)]],
                      constant float4 &src [[buffer(0)]]) {
    MRTOut o;
    o.c0 = d0 * 2.0 + src;
    o.c1 = d1 * 4.0 - src;
    return o;
}

// F-VARY: reads the interpolated varying the vertex stage wrote. Used as the
// fragment half of the two vertex carriers so a spliced vertex field shows up
// in the pixel (either through the varying value or through the geometry).
fragment float4 f_vary(VOutA in [[stage_in]]) { return in.va; }
fragment float4 f_varyc(VOutC in [[stage_in]]) { return in.vc; }

// F-ROG: raster-order-group carrier. A TEXTURE-tagged raster_order_group is the
// shape EXP-0093 showed compiles to the dedicated `pixel_order` acquire/release
// pair (07 14 54 50 06 00 / 07 04 54 d0 06 00); a BUFFER-tagged group uses a
// different mechanism. Every instance covers the same texel, so N instances
// perform N read-modify-writes that the pixel_order pair must serialise: the
// texel ends at exactly N*src if ordering held, and less if it did not.
fragment float4 f_rog(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]],
                      texture2d<float, access::read_write> acc
                          [[texture(0), raster_order_group(0)]]) {
    float4 v = acc.read(uint2(0, 0));
    v = v + src;
    acc.write(v, uint2(0, 0));
    return v + dst;
}

// F-SAMP: per-sample interpolation forces sample-rate execution and compiles to
// `n3_sample_read` (03 xx 26 ..) as the program's first instruction.
fragment float4 f_samp(VOutS in [[stage_in]], constant float4 &src [[buffer(0)]]) {
    return in.a * 2.0 + src;
}
