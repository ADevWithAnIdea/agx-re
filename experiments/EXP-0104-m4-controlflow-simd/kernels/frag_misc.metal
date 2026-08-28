// frag_misc.metal -- EXP-0104 authored MSL: fragment-stage SIMD-05 (quad
// geometric neighbor mapping) and SIMD-07 (helper-lane vote/ballot
// exclusion) probes. Own-authored MSL only (OWN-SHADER). No Apple binary
// read or copied. Rendered via tools/shdump --render + tools/agxtest
// agxrender (pixel readback only). agxrender.m (read-only tool) binds NO
// fragment buffers/uniforms -- every parameter that would otherwise be a
// runtime argument (shuffle mode, discard coordinate) is instead a
// COMPILE-TIME-fixed separate named function, one per case.
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; };

// full-screen triangle, no vertex buffer (same idiom as EXP-0008/EXP-0091's
// harnesses and this experiment's own smoke_render.metal).
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); return o;
}

// ---------------------------------------------------------------------------
// SIMD-05 geometric: each fragment encodes its OWN integer pixel coordinate
// as code = x*16+y (fits one byte for small targets), then reports its
// QUAD PARTNER's code (via quad_shuffle_xor mask 1/2/3, or
// quad_shuffle_up/down) instead of its own. Reading back every pixel's
// reported partner code and comparing to the TRUE screen-space neighbor at
// (x^1,y) / (x,y^1) / (x^1,y^1) determines whether xor-mask 1/2/3 is
// horizontal/vertical/diagonal.
fragment float4 f_quad_selfcode(VOut in [[stage_in]]) {
    int x = (int)in.pos.x;
    int y = (int)in.pos.y;
    int code = x * 16 + y;
    return float4(float(code) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_quad_xor1(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    int code = x * 16 + y;
    int partner = quad_shuffle_xor(code, 1);
    return float4(float(partner) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_quad_xor2(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    int code = x * 16 + y;
    int partner = quad_shuffle_xor(code, 2);
    return float4(float(partner) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_quad_xor3(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    int code = x * 16 + y;
    int partner = quad_shuffle_xor(code, 3);
    return float4(float(partner) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_quad_up1(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    int code = x * 16 + y;
    int partner = quad_shuffle_up(code, 1);
    return float4(float(partner) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_quad_down1(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    int code = x * 16 + y;
    int partner = quad_shuffle_down(code, 1);
    return float4(float(partner) / 255.0, 0.0, 0.0, 1.0);
}

// ---------------------------------------------------------------------------
// SIMD-07: does simd_active_threads_mask correctly EXCLUDE a demoted
// (discarded) helper lane? A FIXED pixel (0,0) discards in the "onediscard"
// kernel; every surviving pixel reports popcount(simd_active_threads_mask())
// in the red channel (0..32 fits one byte). Compare against the
// discard-absent baseline (f_ballot_baseline, byte-identical otherwise).
fragment float4 f_ballot_baseline(VOut in [[stage_in]]) {
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_ballot_onediscard(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) {
        discard_fragment();
    }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}

// Diagnostic follow-up: raw low-16-bits of the active-thread mask (not just
// popcount) in R (low byte) + G (high byte), to sharpen interpretation of
// the popcount(f_ballot_*) results.
fragment float4 f_ballot_baseline_raw(VOut in [[stage_in]]) {
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint lo = (uint)(m & 0xffu);
    uint hi = (uint)((m >> 8) & 0xffu);
    return float4(float(lo) / 255.0, float(hi) / 255.0, 0.0, 1.0);
}
fragment float4 f_ballot_onediscard_raw(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint lo = (uint)(m & 0xffu);
    uint hi = (uint)((m >> 8) & 0xffu);
    return float4(float(lo) / 255.0, float(hi) / 255.0, 0.0, 1.0);
}
