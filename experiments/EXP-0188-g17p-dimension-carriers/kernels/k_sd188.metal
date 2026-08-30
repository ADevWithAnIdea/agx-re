// EXP-0188 SIMD carriers -- THE EXECUTION-MASK-BANK DIMENSION. AUTHORED BY US (OWN-SHADER).
//
// TARGET FIELDS: `simd_ballot.cache` (byte+2, 8 bits) and `simd_shuffle.cache`
// (byte+2 bit 1, ONE bit of a byte whose other bits are match constants:
// simd_shuffle's byte+2 is 0x54 in every occurrence ever observed, and 0x56 is
// the only other value the descriptor can express).
//
// WHY A NEW CARRIER IS NEEDED, AND WHY THIS DIMENSION. EXP-0163 held both
// INERT-ROBUST across 3-4 carriers built for the dimension the NAME suggests --
// operand reuse / last-use:
//   * `k_scache` maximises reuse distance: every SIMD result is consumed many
//     times, one shuffle's result is the next shuffle's lane selector, a loop
//     re-reads them, nothing is dead;
//   * `k_sdiv` adds ONE level of data-dependent divergence;
//   * `k_sball`, `k_stype` vary form and data width.
// The reuse dimension is therefore already spanned, and going further along it
// would be an eighth arm that cannot express the field.
//
// THE DIMENSION THIS FILE ADDS IS THE MASK BANK, on a structural observation
// about the byte itself rather than about the field's NAME:
//
//     simd_shuffle byte+2  == 0x54, with `cache` the 0x02 bit  -> 0x54 / 0x56
//     if_push      byte+2  == 0x54 / 0x56   ("mask bank", nesting parity)
//     jump_cond    byte+2  == 0x54 / 0x64   ("reconvergence mask bank")
//     mask_op      byte+2  == 0x04 / 0x24   ("execution-mask bank selector")
//     pop_reconverge scope == 0x04 / 0x24   (same low-form bank selector)
//
// Four control-flow descriptors in this ISA put an execution-mask BANK SELECTOR
// at byte+2 with exactly this 0x54/0x56-style low form. The hypothesis is that
// `simd_shuffle`'s and `simd_ballot`'s byte+2 is the SAME selector -- naming
// which execution-mask bank the cross-lane network reads its ACTIVE SET from --
// and not a cache hint at all. A program whose active set is the full 32 lanes,
// or which is only ever one region deep, cannot distinguish two mask banks: they
// hold the same mask BY CONSTRUCTION. That is the `iter_at.loc` failure
// (EXP-0164: eight carriers at samples=1 are one carrier) transposed onto
// divergence depth.
//
//   k_sd_flat   no divergence                     depth 0  (bank-indistinguishable)
//   k_sd_n1     one if/else                       depth 1
//   k_sd_n2     if/else inside if/else            depth 2
//   k_sd_n3     three levels of if/else           depth 3
//   k_sd_loop   SIMD ops inside nested memory-bounded loops (loop-iter regions,
//               where the active set SHRINKS between iterations)
//
// ORACLE, and why every cross-lane op used here is exactly host-computable:
//   * every divergence condition tests bit 2, 3 or 4 of the lane id, so the
//     active set is always a union of whole 4-lane QUADS;
//   * `simd_shuffle_xor(v, 1)` and `(v, 2)` therefore always read a lane inside
//     the same quad, hence always an ACTIVE lane -- never undefined;
//   * `simd_ballot(p)` is scored against active-lanes-only semantics: bit L set
//     iff lane L is active AND p(L). This is the one assumption in the file and
//     it is CALIBRATED PRE-FREEZE against the unmutated carrier (raw/prefreeze);
//     a carrier whose unmutated baseline does not match its oracle is dropped
//     before the contract is frozen, not repaired afterwards.
//
// out[32] is the INTEGRITY SENTINEL, stored before any divergent region.
// out[33..39] are never stored and must stay POISON.
#include <metal_stdlib>
using namespace metal;

#define SENT out[32] = 0x5A5A1234u;

// The body every carrier runs at its innermost divergence level. `tag` keeps the
// branches distinguishable so "the mask narrowed differently" is separable from
// "a cross-lane op returned something else".
static inline uint sdbody(uint u, uint tag) {
    uint x1 = simd_shuffle_xor(u, 1u);
    uint x2 = simd_shuffle_xor(u, 2u);
    uint bm = uint(static_cast<simd_vote::vote_t>(simd_ballot((u & 1u) != 0u)));
    return x1 * 3u + x2 * 5u + bm + tag;
}

kernel void k_sd_flat(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *n [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = sdbody(a[t], 1u);
}

kernel void k_sd_n1(device uint *out [[buffer(0)]],
                    device const uint *a [[buffer(1)]],
                    device const uint *n [[buffer(2)]],
                    uint t [[thread_position_in_grid]]) {
    SENT
    uint u = a[t];
    if ((t & 4u) != 0u) { out[t] = sdbody(u, 1u); }
    else                { out[t] = sdbody(u, 2u); }
}

kernel void k_sd_n2(device uint *out [[buffer(0)]],
                    device const uint *a [[buffer(1)]],
                    device const uint *n [[buffer(2)]],
                    uint t [[thread_position_in_grid]]) {
    SENT
    uint u = a[t];
    if ((t & 4u) != 0u) {
        if ((t & 8u) != 0u) { out[t] = sdbody(u, 1u); }
        else                { out[t] = sdbody(u, 2u); }
    } else {
        if ((t & 8u) != 0u) { out[t] = sdbody(u, 3u); }
        else                { out[t] = sdbody(u, 4u); }
    }
}

kernel void k_sd_n3(device uint *out [[buffer(0)]],
                    device const uint *a [[buffer(1)]],
                    device const uint *n [[buffer(2)]],
                    uint t [[thread_position_in_grid]]) {
    SENT
    uint u = a[t];
    if ((t & 4u) != 0u) {
        if ((t & 8u) != 0u) {
            if ((t & 16u) != 0u) { out[t] = sdbody(u, 1u); }
            else                 { out[t] = sdbody(u, 2u); }
        } else {
            if ((t & 16u) != 0u) { out[t] = sdbody(u, 3u); }
            else                 { out[t] = sdbody(u, 4u); }
        }
    } else {
        if ((t & 8u) != 0u) {
            if ((t & 16u) != 0u) { out[t] = sdbody(u, 5u); }
            else                 { out[t] = sdbody(u, 6u); }
        } else {
            if ((t & 16u) != 0u) { out[t] = sdbody(u, 7u); }
            else                 { out[t] = sdbody(u, 8u); }
        }
    }
}

kernel void k_sd_loop(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *n [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint u   = a[t];
    uint acc = u;
    uint n1  = n[96u + t];              // QUAD-UNIFORM trip count, 1..4
    for (uint i = 0u; i < n1; i++) {
        uint bm = uint(static_cast<simd_vote::vote_t>(simd_ballot((u & 1u) != 0u)));
        uint x1 = simd_shuffle_xor(acc, 1u);
        acc = acc * 3u + bm + x1;
    }
    out[t] = acc;
}
