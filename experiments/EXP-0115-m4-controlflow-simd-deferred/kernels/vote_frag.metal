// vote_frag.metal -- EXP-0115 item 5: full vote family under discard, and the
// popcount(simd_active_threads_mask()) 16->24 puzzle left UNRESOLVED by
// EXP-0104. Own-authored MSL, no Apple code read.
//
// Design notes:
//  - 4x4 full-screen-triangle render target (same idiom as EXP-0104's
//    frag_misc.metal): 16 real fragments, one simdgroup.
//  - _pc kernels report popcount(mask) in the R channel (fits one byte, <=32).
//  - _raw kernels report the raw mask's low byte (R) and next byte (G)
//    separately, so a bit-level change (not just a count change) is visible.
//  - f_mask_1return is the DECISIVE new control for the popcount puzzle: a
//    divergent RETURN (ordinary predicated/branch control flow, CF-04-style,
//    but NOT discard_fragment()) at the SAME fixed pixel. If popcount jumps by
//    +8 here too, the effect is generic to divergent control flow; if it does
//    NOT jump (stays 16), the effect is discard-SPECIFIC.
//  - f_mask_2discard / f_mask_discard11 vary discard COUNT and LOCATION to
//    test whether any jump scales with count or depends on position.
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); return o;
}

// ---------------------------------------------------------------------------
// simd_active_threads_mask() family: baseline / one-discard / return-control /
// count and location controls.
fragment float4 f_mask_baseline_pc(VOut in [[stage_in]]) {
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_mask_baseline_raw(VOut in [[stage_in]]) {
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint lo = (uint)(m & 0xffu);
    uint hi = (uint)((m >> 8) & 0xffu);
    return float4(float(lo) / 255.0, float(hi) / 255.0, 0.0, 1.0);
}
fragment float4 f_mask_1discard_pc(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_mask_1discard_raw(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint lo = (uint)(m & 0xffu);
    uint hi = (uint)((m >> 8) & 0xffu);
    return float4(float(lo) / 255.0, float(hi) / 255.0, 0.0, 1.0);
}
// decisive control: divergent RETURN, no discard, same fixed pixel.
fragment float4 f_mask_1return_pc(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { return float4(0.0, 1.0, 0.0, 1.0); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
// discard COUNT control: two fixed pixels discard.
fragment float4 f_mask_2discard_pc(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if ((x == 0 && y == 0) || (x == 3 && y == 3)) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
// discard LOCATION control: single discard at a different pixel (1,1) instead
// of the corner (0,0).
fragment float4 f_mask_discard11_pc(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 1 && y == 1) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}

// ---------------------------------------------------------------------------
// simd_all(): predicate is FALSE only at the discarding pixel (0,0). If the
// demoted lane's predicate still counts (inclusion), simd_all reads FALSE for
// every surviving pixel; if excluded, TRUE.
fragment float4 f_all_baseline(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = !(x == 0 && y == 0);
    bool r = simd_all(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}
fragment float4 f_all_1discard(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = !(x == 0 && y == 0);
    if (x == 0 && y == 0) { discard_fragment(); }
    bool r = simd_all(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}

// ---------------------------------------------------------------------------
// simd_any(): predicate is TRUE only at the discarding pixel. If included,
// simd_any reads TRUE for survivors; if excluded, FALSE.
fragment float4 f_any_baseline(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = (x == 0 && y == 0);
    bool r = simd_any(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}
fragment float4 f_any_1discard(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = (x == 0 && y == 0);
    if (x == 0 && y == 0) { discard_fragment(); }
    bool r = simd_any(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}

// ---------------------------------------------------------------------------
// simd_ballot(predicate) explicit form (distinct db.json pred=1 encoding from
// simd_active_threads_mask's pred=0 form, EXP-M4-13): predicate uniformly
// TRUE, so an inclusive reading should reproduce the SAME popcount (and the
// same discard-triggered jump, if any) as simd_active_threads_mask.
fragment float4 f_ballotpred_baseline_pc(VOut in [[stage_in]]) {
    uint64_t m = (uint64_t)simd_ballot(true);
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_ballotpred_1discard_pc(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_ballot(true);
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
