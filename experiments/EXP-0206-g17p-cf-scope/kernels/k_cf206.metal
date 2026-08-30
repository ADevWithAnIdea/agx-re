// EXP-0206 control-flow (divergent-region) carriers. AUTHORED BY US (OWN-SHADER).
//
// TARGET FIELDS carried here:
//   `if_push.scope`            byte+2 of `0f 05 <scope> <kind>`      (4 B)
//   `pop_reconverge.scope`     byte+2 of `0f 06 <scope> <kind> <r16>` (6 B)
//   `pop_reconverge.reserved`  bytes+4..5 of the same word
//   `stop.reserved`            bits 8..31 of `0e <r24>`              (4 B)
//
// WHY THESE SHAPES. EXP-0184 swept `if_push.scope` over 2560 dispatches at
// nesting depth 1..3 and got 0/256 movement, and named its own gap: every one of
// its ten occurrences was `0f 05 54 01` -- a CONDITIONAL-SKIP push. db.json's
// 0x54/0x56 "nesting parity" claim comes from LOOP-ITERATION pushes
// (`scope_kind == 0x1a`) that EXP-0184 never reached. EXP-0188 built carriers of
// this shape, confirmed by census that all six emit `scope_kind == 0x1a`, and
// found in pre-freeze calibration that at those occurrences 0x00/0x54 FAULT while
// 0x56/0xFF are correct -- but its gated pair never ran (the neo went
// unreachable), so nothing was promoted. THIS FILE RE-AUTHORS THAT CARRIER AXIS
// so the gated pair can be completed. Shape (not values, not oracles) cited from
// experiments/EXP-0188-g17p-dimension-carriers/kernels/k_cf188.metal.
//
// The essential trick, and the reason EXP-0184's loops emitted no push at all:
// the trip counts are LOADED FROM DEVICE MEMORY, so they are opaque to the
// compiler and the loops cannot be unrolled or flattened, and the loops are
// NESTED -- the L1/L2/L3 ladder db.json's own provenance names.
//
// DISPATCH GEOMETRY IS LOAD-BEARING (EXP-0179): an unconditional `if_push` with
// `scope_kind == 0x01` masks off the only lane of a ONE-THREAD dispatch in both
// mask banks, collapsing "the mask narrowed" and "the mask narrowed differently"
// into one dead dispatch. Every carrier here is grid 32 / threadgroup 32 and the
// observable is the whole 32-lane vector, so a mask-bank difference is visible as
// a DIFFERENT SET OF LANES, not merely as an absent result.
//
// THE OBSERVABLE DOES NOT CO-VARY WITH THE FIELD (FIELD-SWEEP-PROTOCOL 3a):
// `scope` selects a reconvergence mask bank; the observable is 32 per-lane words
// at FIXED addresses that no value of the field can name or relocate.
//
// ARITHMETIC IS INTEGER, DELIBERATELY: acc = acc*3 + 7 (mod 2^32) is bit-exact on
// the host for any iteration count, so the oracle is computed by simulating OUR
// OWN MSL and never read back from the GPU. Every expected value is non-zero,
// because Apple9's characteristic failure is a SILENT ZERO and a zero oracle
// would score a silent zero as a pass.
//
// out[32] is an INTEGRITY SENTINEL stored BEFORE any divergent region is entered,
// through a path independent of every instruction under test, so it survives even
// if every lane is later masked off. out[33..39] are never stored by any carrier
// and must read back as their own POISON.
#include <metal_stdlib>
using namespace metal;

#define SENT out[32] = 0x5A5A1234u;

// n[t]       -> outer trip count  (1..4)
// n[32u + t] -> inner trip count  (1..3)
// n[64u + t] -> third trip count  (1..2)

// C1: two nested memory-bounded loops -> loop-iteration pushes at depth 2.
kernel void k_cf_nl2(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *n [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    uint acc = a[t];
    uint n1 = n[t], n2 = n[32u + t];
    for (uint i = 0u; i < n1; i++)
        for (uint j = 0u; j < n2; j++)
            acc = acc * 3u + 7u;
    out[t] = acc;
}

// C2: three nested memory-bounded loops -> loop-iteration pushes at depth 3.
kernel void k_cf_nl3(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *n [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    uint acc = a[t];
    uint n1 = n[t], n2 = n[32u + t], n3 = n[64u + t];
    for (uint i = 0u; i < n1; i++)
        for (uint j = 0u; j < n2; j++)
            for (uint k = 0u; k < n3; k++)
                acc = acc * 3u + 7u;
    out[t] = acc;
}

// C3: an if/else INSIDE two nested loops -> both region kinds in one program,
// which is the mixed case a bank selector would have to keep apart.
kernel void k_cf_nlif(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *n [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint acc = a[t];
    uint n1 = n[t], n2 = n[32u + t];
    for (uint i = 0u; i < n1; i++) {
        for (uint j = 0u; j < n2; j++) {
            if (((acc >> (j & 7u)) & 1u) != 0u) { acc = acc * 3u + 7u; }
            else                                { acc = acc * 5u + 11u; }
        }
    }
    out[t] = acc;
}

// C4: while(true)+break, nested twice -> a loop-iteration region reached through
// a break edge rather than a counted latch.
kernel void k_cf_wbrk(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *n [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint acc = a[t];
    uint n1 = n[t], n2 = n[32u + t];
    uint i = 0u;
    while (true) {
        if (i >= n1) { break; }
        uint j = 0u;
        while (true) {
            if (j >= n2) { break; }
            acc = acc * 3u + 7u;
            j++;
        }
        i++;
    }
    out[t] = acc;
}

// C5: two nested loops INSIDE an if/else -> a conditional-skip scope enclosing
// loop-iteration scopes, i.e. deliberate nesting-parity pressure. The if tests
// the LANE ID, so the two arms are executed by disjoint halves of the SIMD group
// and a mask-bank error shows up as the wrong lanes, not merely a wrong value.
kernel void k_cf_ifnl(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *n [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint acc = a[t];
    uint n1 = n[t], n2 = n[32u + t];
    if ((t & 1u) != 0u) {
        for (uint i = 0u; i < n1; i++)
            for (uint j = 0u; j < n2; j++)
                acc = acc * 3u + 7u;
    } else {
        for (uint i = 0u; i < n2; i++)
            acc = acc * 5u + 11u;
    }
    out[t] = acc;
}

// C6: nested loops with a `continue` edge -> the narrowing re-entry a mask bank
// has to restore mid-body rather than at a block end.
kernel void k_cf_lcont(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       device const uint *n [[buffer(2)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    uint acc = a[t];
    uint n1 = n[t], n2 = n[32u + t];
    for (uint i = 0u; i < n1; i++) {
        for (uint j = 0u; j < n2; j++) {
            if (((t >> (j & 7u)) & 1u) == 0u) { continue; }
            acc = acc * 3u + 7u;
        }
        acc = acc + 1u;
    }
    out[t] = acc;
}
