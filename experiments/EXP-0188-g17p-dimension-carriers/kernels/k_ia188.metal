// EXP-0188 integer-add carriers -- THE OPERAND-FORMAT DIMENSION. AUTHORED BY US (OWN-SHADER).
//
// TARGET FIELD: `iadd2.b2_fmt` = instruction bits 18..23, i.e. the TOP SIX BITS
// of byte+2 (byte+2 = b2_bit0 | store_en<<1 | b2_fmt<<2).
//
// WHY A NEW CARRIER IS NEEDED. EXP-0171 swept all 64 sub-values DENSE and got
// 0/64, on ONE carrier: `NAT:k_u32add`, a plain 32-bit unsigned add of two
// values loaded from memory. Its detection-power argument is airtight and worth
// repeating, because it is what makes the null result meaningful at all --
// "byte+2 itself moves 128 of 256 on the NAT carrier ... so the byte is
// demonstrably live and b2_fmt really is inert" -- but that movement is bits 0..1
// (`b2_bit0` / `store_en`). Nothing in that experiment varied the one thing the
// field's NAME points at: the operand FORMAT.
//
// So the dimension this file adds is OPERAND FORMAT / WIDTH:
//
//   k_ia_u32     32-bit unsigned, both operands in registers   (EXP-0171's shape)
//   k_ia_s32     32-bit SIGNED                                 (db.json claims
//                signed and unsigned are BYTE-IDENTICAL -- a census check of a
//                documented claim, free of device time if it holds)
//   k_ia_u16     16-bit unsigned add
//   k_ia_u64     64-bit add over a register PAIR (EXP-0146 HW-validated that a
//                native single-instruction 64-bit add exists in this family)
//   k_ia_imm     32-bit add with an INLINE IMMEDIATE srcB (db.json: the
//                reg-vs-immediate srcB TYPE flips opc_tail/opc_tail2 and srcA --
//                a format distinction the descriptor already documents)
//   k_ia_uni     one operand read from a UNIFORM address (db.json: a uniform
//                srcB sets byte+5 bit 4, a uniform srcA sets byte+6)
//   k_ia_chain   two dependent adds, so the second one's result is consumed by a
//                further ALU op rather than going straight to memory
//
// If the compiler's own `b2_fmt` value DIFFERS across these carriers, the field
// is a format selector and the census says so before any device time. If it is
// constant across every width and operand class we can reach AND still inert
// under a dense sweep, that is a far stronger negative than EXP-0171's, because
// the carriers provably span the dimension.
//
// THE OBSERVABLE DOES NOT CO-VARY WITH THE FIELD (protocol 3a): the swept bits
// are inside byte+2 of the add; the observable is eight result words at fixed
// addresses written by a separate store.
//
// SEEDING (dispatch rule): operands arrive from device memory here because that
// is what makes the carriers differ in WIDTH, but nothing in this file seeds a
// value FROM a `device_load` into a spliced instruction's source -- the splice is
// on the add's own byte+2, and the read-back is poisoned, so an asynchronous load
// cannot fabricate movement against a refreshed baseline.
//
// out[8] is the INTEGRITY SENTINEL; out[9..15] are never stored and stay POISON.
// Every expected value is NON-ZERO by construction (checked on the host).
#include <metal_stdlib>
using namespace metal;

#define SENT8 out[8] = 0x5A5A1234u;

kernel void k_ia_u32(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT8
    out[t] = a[t] + b[t];
}

kernel void k_ia_s32(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT8
    int x = as_type<int>(a[t]) + as_type<int>(b[t]);
    out[t] = as_type<uint>(x);
}

kernel void k_ia_u16(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT8
    ushort x = ushort(a[t] & 0xFFFFu) + ushort(b[t] & 0xFFFFu);
    out[t] = uint(x);
}

kernel void k_ia_u64(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT8
    ulong s = (ulong(a[t]) << 16) + (ulong(b[t]) << 32);
    out[t] = uint(s >> 24) ^ uint(s & 0xFFFFFFFFul);
}

kernel void k_ia_imm(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT8
    out[t] = a[t] + 1234u;
}

kernel void k_ia_uni(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT8
    out[t] = a[t] + b[0];
}

kernel void k_ia_chain(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       device const uint *b [[buffer(2)]],
                       uint t [[thread_position_in_grid]]) {
    SENT8
    uint x = a[t] + b[t];
    out[t] = x ^ (x + a[t]);
}
