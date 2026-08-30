// EXP-0171 probe kernels -- ALL AUTHORED BY US (clean-room OWN-SHADER).
//
// Two jobs:
//   1. ANCHOR SOURCE. Each kernel is compiled with tools/shdump; the compiled
//      `_agc.main` is tokenized with tools/agx-isa, and a contiguous run of
//      PURE-ALU instructions containing the instruction under test is lifted
//      BYTE-FOR-BYTE into the synthesized SYNTH carrier.
//   2. NAT CARRIER. The same compiled kernel is ALSO used unmodified except for
//      the one swept byte, spliced IN PLACE, so the instruction under test keeps
//      its own operand provenance (values LOADED from buffers, not seeded by
//      mov_imm) and its own consumer (the compiler's own device_store). That is
//      the structurally-different second carrier this experiment needs.
//
// `sent` is the INTEGRITY SENTINEL and lives in its OWN buffer (index 4) so it
// is written through a different base slot from `out`. Both buffers are poisoned
// with 0xDEADBEEF before every dispatch, which is what distinguishes
// "the op produced 0" from "the program never ran"
// (FIELD-SWEEP-PROTOCOL section 7, instrument 1 and 2).
//
// Every kernel keeps the same buffer indices so one harness drives all of them:
//   0 = out (read back, poisoned)   1 = a   2 = b   3 = c   4 = sent (read back)
//
// CLEAN-ROOM: our own MSL. No Apple source was consulted and no Apple binary
// was introspected.
#include <metal_stdlib>
using namespace metal;

#define SENT_A 0x5A5A5A5Au
#define SENT_B 0x0BADF00Du

// ---------------------------------------------------------------------------
// ARM A -- ilogic. `k_and` is the shape EXP-0146 used on M4 (a bitwise op whose
// result is CONSUMED BY A STORE); the rest widen the LUT census so we can see
// which byte+7 values the compiler itself emits.
// ---------------------------------------------------------------------------
kernel void k_and(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                  device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                  uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] & b[g];
    sent[1] = SENT_B;
}

kernel void k_or(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                 device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                 uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] | b[g];
    sent[1] = SENT_B;
}

kernel void k_xor(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                  device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                  uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] ^ b[g];
    sent[1] = SENT_B;
}

kernel void k_andn(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                   device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                   uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] & (~b[g]);
    sent[1] = SENT_B;
}

kernel void k_nand(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                   device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                   uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = ~(a[g] & b[g]);
    sent[1] = SENT_B;
}

// The COMPARE-CONSUMED pole: db.json's ilogic semantics say byte+7 bit7 is set
// on the store-consumed forms and CLEAR on the "dec2" predicate-consumed forms.
// If that is right, one of these two kernels should contain an ilogic whose
// byte+7 has bit7 clear -- a compiler-emitted anchor for the other pole.
kernel void k_and_sel(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                      device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                      uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = ((a[g] & b[g]) != 0u) ? 7u : 9u;
    sent[1] = SENT_B;
}

kernel void k_and_if(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                     device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                     uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    if ((a[g] & b[g]) != 0u) { out[g] = 7u; } else { out[g] = 9u; }
    sent[1] = SENT_B;
}

// ---------------------------------------------------------------------------
// ARM B -- the srcA / tail levers.
// ---------------------------------------------------------------------------
// ibitcount (blocking field: `tail`, byte+7)
kernel void k_popcnt(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                     device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                     uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = popcount(a[g]);
    sent[1] = SENT_B;
}

kernel void k_clz(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                  device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                  uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = clz(a[g]);
    sent[1] = SENT_B;
}

// ibfe (blocking: `srcA` byte+8, `b2_bit0`, `sign_ext`)
kernel void k_bfe(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                  device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                  uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = extract_bits(a[g], 4u, 6u);
    sent[1] = SENT_B;
}

kernel void k_bfe_s(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                    device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                    uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = uint(extract_bits(int(a[g]), 4u, 6u));   // SIGNED -> exercises sign_ext
    sent[1] = SENT_B;
}

// fspecial_est (blocking: `srcA` byte+1, `subop` byte+3).
// EXP-0161 could not promote either because BOTH its carriers were the PRECISE
// forms, where a Newton-Raphson refinement corrects the estimate whatever the
// estimate was. `k_rsqrt_fast` asks for the fast form; and the SYNTH carrier
// lifts the estimate ALONE, with no refinement after it, which is the dimension
// the field controls.
kernel void k_rsqrt(device uint* out [[buffer(0)]], device const float* a [[buffer(1)]],
                    device const float* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                    uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = as_type<uint>(rsqrt(a[g]));
    sent[1] = SENT_B;
}

kernel void k_rsqrt_fast(device uint* out [[buffer(0)]], device const float* a [[buffer(1)]],
                         device const float* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                         uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = as_type<uint>(fast::rsqrt(a[g]));
    sent[1] = SENT_B;
}

kernel void k_recip_fast(device uint* out [[buffer(0)]], device const float* a [[buffer(1)]],
                         device const float* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                         uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = as_type<uint>(fast::divide(1.0f, a[g]));
    sent[1] = SENT_B;
}

// iadd2 (blocking: `srcA` byte+7, `b2_fmt`)
kernel void k_u32add(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                     device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                     uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] + b[g];
    sent[1] = SENT_B;
}

// packed_half2_hi (blocking: `srcA`, `srcB`, `mods`)
kernel void k_half2(device half* out [[buffer(0)]], device const half* a [[buffer(1)]],
                    device const half* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                    uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    half2 x = half2(a[2u * g], a[2u * g + 1u]);
    half2 y = half2(b[2u * g], b[2u * g + 1u]);
    half2 r = x * y + x;
    out[2u * g] = r.x;
    out[2u * g + 1u] = r.y;
    sent[1] = SENT_B;
}

// icmp_pred (blocking: `srcA`, `neg`, `srcB`, `opclass`). The predicate is only
// observable through a divergent block, so this kernel is used in NAT mode.
kernel void k_cmpsel(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                     device const uint* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                     uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    if (a[g] < b[g]) { out[g] = 21u; } else { out[g] = 34u; }
    sent[1] = SENT_B;
}

// bf_alu / bf_fma_dst (blocking: `srcA`, `srcB`, `tail` / `tail`)
kernel void k_bfadd(device bfloat* out [[buffer(0)]], device const bfloat* a [[buffer(1)]],
                    device const bfloat* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                    uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] + b[g];
    sent[1] = SENT_B;
}

kernel void k_bfmul(device bfloat* out [[buffer(0)]], device const bfloat* a [[buffer(1)]],
                    device const bfloat* b [[buffer(2)]], device uint* sent [[buffer(4)]],
                    uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] * b[g];
    sent[1] = SENT_B;
}

kernel void k_bffma(device bfloat* out [[buffer(0)]], device const bfloat* a [[buffer(1)]],
                    device const bfloat* b [[buffer(2)]], device const bfloat* c [[buffer(3)]],
                    device uint* sent [[buffer(4)]], uint g [[thread_position_in_grid]]) {
    sent[0] = SENT_A;
    out[g] = a[g] * b[g] + c[g];
    sent[1] = SENT_B;
}
