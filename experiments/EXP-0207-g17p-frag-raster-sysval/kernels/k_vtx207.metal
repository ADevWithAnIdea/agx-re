// k_vtx207.metal -- EXP-0207 VERTEX-stage carriers for vtx_coord_xform.operand.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY THESE SHAPES.  EXP-0147 dispatched `operand` (bytes 5..9, 40 bits) on ONE
// vertex carrier -- an indexed constant array plus a uniform -- into a 2x2 pixel
// read-back, and EXP-0193 withdrew the field this morning because that produced
// exactly **1 distinct VALID payload across 817 legal values**: the movement was
// 987 no_draw plus 39 fault, a reproducible hazard map rather than a semantic.
//
// A carrier holding ONE selectable coordinate source cannot produce a second
// valid payload no matter how many values are dispatched: every legal
// alternative selection has nothing else to select.  So every carrier here holds
// SEVERAL mutually distinguishable indexed-constant sources, and the read-back is
// 16x16 raw bytes instead of 2x2 floats, so a different-but-legal coordinate
// shows up as a different payload instead of collapsing into `no_draw`.
//
// `vtx_coord_xform` is byte0 0x17 with byte+2 0xa2 / byte+3 0xb0, and it is the
// indexed-constant-array shape that makes the compiler emit it (EXP-0147's own
// finding, reproduced here).  The operand bytes stay RAW: clean-room rule 5
// forbids reconstructing the coordinate-select sequence, so no semantic oracle
// is authored for this field and none is claimed.

#include <metal_stdlib>
using namespace metal;

// Every fragment here writes a COVERAGE SENTINEL to a device buffer the harness
// poisons with 0xDEADBEEF.  It serves two purposes at once: it proves the draw
// happened at all (so a suppressed draw is `no_draw`, a HARD outcome, and never
// silent movement), and because it is written per covered pixel it is also a
// 16x16 COVERAGE MAP -- which is the observable that actually distinguishes one
// legal coordinate selection from another when the position changes.
constant uint SENT_BASE = 0x5A5A0000u;

// v_multi: THREE indexed constant arrays -- one feeding the position and two
// feeding varyings with disjoint value ranges, so a re-selected source is
// visible as a different colour rather than as a lost triangle.
struct VMulti { float4 pos [[position]]; float4 vc; float4 vd; };
vertex VMulti v_multi(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    float4 a[3] = { float4(11, 12, 13, 14), float4(21, 22, 23, 24), float4(31, 32, 33, 34) };
    float4 b[3] = { float4(41, 42, 43, 44), float4(51, 52, 53, 54), float4(61, 62, 63, 64) };
    VMulti o;
    o.pos = float4(p[vid], 0.0, 1.0);
    o.vc  = a[vid] * vp.x;
    o.vd  = b[vid] * vp.y;
    return o;
}
fragment float4 f_multi(VMulti in [[stage_in]], device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 16u + x] = SENT_BASE + y * 16u + x;
    return in.vc + in.vd * 0.03125;
}

// v_wide: ONE array with EIGHT entries, indexed by a runtime-dependent index, so
// there are eight distinct selectable slots rather than three.
struct VWide { float4 pos [[position]]; float4 vc; };
vertex VWide v_wide(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    float4 q[8] = { float4(1, 2, 3, 4),      float4(5, 6, 7, 8),
                    float4(9, 10, 11, 12),   float4(13, 14, 15, 16),
                    float4(17, 18, 19, 20),  float4(21, 22, 23, 24),
                    float4(25, 26, 27, 28),  float4(29, 30, 31, 32) };
    uint k = (vid + uint(vp.z)) & 7u;
    VWide o;
    o.pos = float4(p[vid], 0.0, 1.0);
    o.vc  = q[k] * vp.x + q[(k + 3u) & 7u] * vp.y;
    return o;
}
fragment float4 f_wide(VWide in [[stage_in]], device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 16u + x] = SENT_BASE + y * 16u + x;
    return in.vc;
}

// v_pos2: TWO candidate position arrays, selected by a uniform.  Here a
// re-selected coordinate changes the GEOMETRY, which at 16x16 is a large,
// clearly distinct coverage pattern rather than an all-or-nothing draw.
struct VPos2 { float4 pos [[position]]; float4 vc; };
vertex VPos2 v_pos2(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    float2 r[3] = { float2(-0.75, -0.75), float2(0.75, -0.75), float2(0.0, 0.9) };
    float2 sel = (vp.w > 0.5) ? r[vid] : p[vid];
    VPos2 o;
    o.pos = float4(sel, 0.0, 1.0);
    o.vc  = float4(0.2 + 0.3 * float(vid), 0.7, 0.4 * float(vid), 1.0) * vp.x;
    return o;
}
fragment float4 f_pos2(VPos2 in [[stage_in]], device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 16u + x] = SENT_BASE + y * 16u + x;
    return in.vc;
}
