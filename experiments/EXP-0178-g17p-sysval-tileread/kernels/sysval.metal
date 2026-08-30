// EXP-0178 system-value (`get_sr`) carriers -- OWN-SHADER MSL, authored for this
// experiment. Three STRUCTURALLY DIFFERENT carriers, one per shader stage,
// because EXP-0031 established that the AGX special-register namespace is
// stage-contextual: two carriers in the same stage are ONE carrier for a field
// that selects a special register.
//
// CO-VARIATION AUDIT (FIELD-SWEEP-PROTOCOL section 3a). In every carrier below
// the observable is produced by an instruction the sweep NEVER touches:
//   * compute  -- the value read by the get_sr under test reaches memory through
//                 a LATER, SEPARATE add and a THIRD, SEPARATE device_store whose
//                 index register comes from a DIFFERENT, unspliced get_sr.
//   * fragment -- the value read by the get_sr under test lands in colour
//                 channel .r; channel .g is fed by a DIFFERENT, unspliced get_sr
//                 and channel .a by a uniform alone, so both are integrity
//                 sentinels on paths the instruction under test cannot name.
//   * vertex   -- the get_sr under test feeds a VARYING; the triangle's geometry
//                 is driven by a DIFFERENT, unspliced get_sr, so a spliced
//                 selector can never move the rasterised coverage that the
//                 observation is read from.
// No arm splices the observable's own selector in lockstep with the field under
// test, which is the EXP-0140 / EXP-0168 defect the rule exists to stop.
//
// CLEAN-ROOM: every byte we splice is the compiled form of the source below,
// compiled by the public newLibraryWithSource: API. No Apple binary is
// disassembled, decompiled or introspected.

#include <metal_stdlib>
using namespace metal;

// ============================================================== C_COMPUTE ====
//
// Body identical to our own EXP-0092 `kernels/srprobe.metal` (cited, not
// copied from anyone else), plus a second output buffer carrying an integrity
// sentinel that no special-register read contributes to.
//
// The get_sr UNDER TEST reads [[thread_index_in_simdgroup]] (SR 0x82). A
// separate, later add (+1000) consumes it and a third, separate device_store
// writes the result -- the later-read discipline of
// docs/isa/register-move-and-liveness.md, required after EXP-0086 found a
// producer-side bit that corrupts only a LATER separate instruction's read.
//
// Dispatched at grid=64 / tg=64 (one threadgroup, threadExecutionWidth 32) so
// that distinct special registers produce distinct, HOST-COMPUTABLE 64-thread
// patterns:  simd_lane_id = t%32,  thread_position_in_grid.x = t,
// simd_group_id = t/32,  threads_per_threadgroup.x = 64, and the
// threadgroup_position_in_grid family = 0.  EXP-0169's G17P get_sr arm failed
// its liveness ladder precisely because it ran a lifted probe at grid=1/tg=1,
// where every reachable SR reads 0 and no selector can move anything.
//
// +1000 keeps a genuine zero-valued SR read distinguishable from "the dispatch
// never happened" even before the poison check.
kernel void k_sr_c(device uint* out  [[buffer(0)]],
                   device uint* sent [[buffer(4)]],
                   uint gid [[thread_position_in_grid]],
                   uint v   [[thread_index_in_simdgroup]]) {
    out[gid]  = v + 1000u;
    sent[gid] = 0xA5A5A5A5u;     // integrity sentinel: no SR value contributes
}

// ============================================================= C_FRAGMENT ====

// Full-screen triangle. Geometry comes from [[vertex_id]]; nothing here is ever
// spliced by the fragment arm.
struct VOutP { float4 pos [[position]]; };
vertex VOutP v_full(uint vid [[vertex_id]]) {
    VOutP o;
    o.pos = float4((vid == 2) ? 3.0 : -1.0, (vid == 1) ? 3.0 : -1.0, 0.0, 1.0);
    return o;
}

// f_sr: the fragment [[position]] read lowers to two get_sr (EXP-0031 / EXP-0177:
// 0xa0 = integer pixel X, 0xa1 = integer pixel Y) plus a pixel-centre fixup this
// project has not yet identified.
//
//   .r  <- pos.x   : the get_sr UNDER TEST (baseline selector 0xa0)
//   .g  <- pos.y   : a DIFFERENT, unspliced get_sr -> integrity sentinel #1
//   .b  <- pos.x*4 + src.x : a second, differently scaled reading of the value
//                            under test (detects an aliased or partial write)
//   .a  <- src.y   : uniform only -> integrity sentinel #2 (proves the fragment
//                    ran and the colour store executed, with no SR involved)
//
// Rendered at 4x4 so pixel X and pixel Y give DIFFERENT 16-pixel patterns: the
// 0xa0 <-> 0xa1 mutual swap is then a host-computable litmus that the
// measurement can see a selector change at all (the EXP-M4-14 method).
fragment float4 f_sr(float4 pos [[position]], constant float4 &src [[buffer(0)]]) {
    return float4(pos.x, pos.y, pos.x * 4.0 + src.x, src.y);
}

// =============================================================== C_VERTEX ====

// v_sr: TWO special-register reads with different roles.
//   * [[vertex_id]] (SR 0xdd) drives the triangle's geometry and is NEVER
//     spliced, so the rasterised coverage is constant across the whole sweep.
//     `vid % 3` keeps the geometry correct under a non-zero baseVertex.
//   * [[instance_id]] (SR 0xd8) is the get_sr UNDER TEST; it feeds an
//     interpolated varying that the fragment stage passes straight through.
//
// Drawn INDEXED with indices {0,1,2}, baseVertex 9, baseInstance 5,
// instanceCount 3, so the four vertex-stage system values are mutually
// distinguishable in the read-back:
//     vertex_id   (0xdd) -> 9,10,11 at the three corners = a spatial RAMP
//     instance_id (0xd8) -> 5,6,7; last instance wins    = FLAT 7
//     base_vertex (0x88) -> FLAT 9
//     base_instance(0x8a)-> FLAT 5
// and any unpopulated selector reads flat 0. `[[base_vertex]]`/`[[base_instance]]`
// are HW-VALIDATED on M4 only (EXP-0092); this carrier is what puts them on G17P.
struct VOutS { float4 pos [[position]]; float4 sv; };
vertex VOutS v_sr(uint vid [[vertex_id]], uint iid [[instance_id]]) {
    uint k = vid % 3u;
    VOutS o;
    o.pos = float4((k == 2) ? 3.0 : -1.0, (k == 1) ? 3.0 : -1.0, 0.0, 1.0);
    o.sv  = float4(float(iid), 0.0, 0.0, 1.0);
    return o;
}

fragment float4 f_sv(VOutS in [[stage_in]], constant float4 &src [[buffer(0)]]) {
    // .r = the interpolated system value under test.
    // .a = uniform only -> integrity sentinel on a path with no SR in it.
    return float4(in.sv.x, in.sv.y, in.sv.z, src.y);
}
