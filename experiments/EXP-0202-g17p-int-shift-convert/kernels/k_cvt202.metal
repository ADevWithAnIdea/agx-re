// EXP-0202 float->integer convert carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET: `cvt_f2i.b9` (byte+9) and the instruction-level `_instruction` label.
//
// THE REFUSAL THIS FILE ANSWERS, quoted from EXP-0168/PROGRESS.md:249 --
//   "(g) `cvt_f2i.b9` is INERT-SINGLE, not UNSTABLE -- 256/256 `ok` in BOTH runs,
//    one distinct observed word, rv01 unanimous. Like `copysign.operands` it does
//    not need a third run; it needs a second, structurally different carrier."
//
// EXP-0184 then supplied five carriers -- s32, u32, s16, u16, h32 -- and every one
// of them varies DESTINATION WIDTH / SIGN or SOURCE WIDTH. That is the dimension
// db.json already assigns to byte+8 (`dst_class`) and byte+4 (`src_class`). For
// byte+9, five carriers that vary byte+8's dimension are still ONE carrier.
//
// The dimensions below have never been varied for this field:
//   k_cvt_alu   result CONSUMED BY A FOLLOWING ALU op   (result routing; every
//               EXP-0184 carrier stored the result straight to memory)
//   k_cvt_i64   64-bit destination -- a register PAIR   (width beyond 32)
//   k_cvt_uni   source is a THREAD-INVARIANT constant   (source class)
//   k_cvt_v4    four converts in one vector expression  (vector form)
//   k_cvt_rnd   rint() then convert                     (rounding path)
//   k_cvt_s32   float -> int, stored                    (the EXP-0184 baseline,
//                                                        re-run here as the
//                                                        comparison point)
//
// SECOND, INDEPENDENT PURPOSE: byte+9 is the last byte of the modelled 10-byte
// length. `analysis/census.py` reports where the pinned tokenizer says the NEXT
// instruction starts. If the length model is wrong and byte+9 is the following
// instruction's leader, sweeping it will not be quietly inert. Either way it is a
// first-class result.
//
// `_instruction`: EXP-0013 established on M4/A18 that this converts by TRUNCATION
// TOWARD ZERO and that splicing `signflag` bit 6 (0x40) turns the signed convert
// into the unsigned one. Never re-run on G17P. The oracle for that arm is TWO
// COMPETING host-computed vectors (signed-truncation and unsigned-truncation,
// which differ on the negative lanes), and the case is scored by WHICH it matched.
//
// ORACLE inputs:
//   f[t] = {3.9, -3.9, 2.5, -2.5, 100.75, 7.0, 0.5, 63.25}
//   g[t] = {3.9, 12.25, 2.5, 250.5, 100.75, 7.0, 1.5, 63.25}
// Lane 6 of f truncates to 0 and is the one lane where a silent zero is
// indistinguishable from a pass; it is EXCLUDED from the match test and reported
// separately, exactly as EXP-0184 did.
//
// SENTINEL out[8] = 12345 (out[16] in the 64-bit carrier), written first.
// POISON on buffer 0. CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 12345u;

kernel void k_cvt_s32(device uint *out [[buffer(0)]],
                      device const float *f [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = uint(int(f[t]));
}

kernel void k_cvt_alu(device uint *out [[buffer(0)]],
                      device const float *f [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = uint(int(f[t]) * 3 + 7);
}

kernel void k_cvt_uni(device uint *out [[buffer(0)]],
                      device const float *f [[buffer(1)]],
                      constant float &s [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = uint(int(s) * 1000 + int(t) + 1);
}

kernel void k_cvt_v4(device uint *out [[buffer(0)]],
                     device const float *f [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    float4 v = float4(f[t], f[t] * 2.0f, f[t] * 4.0f, f[t] * 8.0f);
    int4 iv = int4(v);
    out[t] = uint(iv.x + iv.y * 3 + iv.z * 5 + iv.w * 7);
}

kernel void k_cvt_rnd(device uint *out [[buffer(0)]],
                      device const float *f [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = uint(int(rint(f[t])) + 1);
}

// 64-bit destination: a register PAIR. out[16] is the sentinel here because the
// value region is 16 words (8 lanes x lo/hi).
kernel void k_cvt_i64(device uint *out [[buffer(0)]],
                      device const float *f [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    out[16] = 12345u;
    long v = long(f[t] * 1048576.0f) + 0x300000005L;
    ulong u = as_type<ulong>(v);
    out[2 * t + 0] = uint(u & 0xFFFFFFFFul);
    out[2 * t + 1] = uint(u >> 32);
}

// Instruction-level arm for H8 (`cvt_f2i._instruction`). Lane 7 of its input is
// 2147483904.0 = 2^31 + 2^8, exactly representable in f32 and OUTSIDE int32's
// range: a SIGNED convert and an UNSIGNED convert cannot agree there. Lane 7 is
// excluded from the baseline match test (its signed value is not defined by the
// language) and its observed word is recorded, so splicing `signflag` bit 6 is
// scored against TWO COMPETING host-computed vectors rather than against "was it
// still correct".
kernel void k_cvt_sgn(device uint *out [[buffer(0)]],
                      device const float *g [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = uint(int(g[t]));
}
