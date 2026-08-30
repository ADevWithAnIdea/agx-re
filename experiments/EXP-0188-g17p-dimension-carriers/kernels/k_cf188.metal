// EXP-0188 control-flow carriers -- THE REGION-KIND DIMENSION. AUTHORED BY US (OWN-SHADER).
//
// TARGET FIELD: `if_push.scope` = byte+2 of the 4-byte `0f 05 <scope> <kind>`.
// db.json models it as the reconvergence MASK BANK, "ping-pongs 0x54/0x56 with
// nesting parity", and its provenance (EXP-M4-13 R6, M4, compile-only byte-diff)
// comes from a LOOP-NESTING ladder in which every push carried
// `scope_kind == 0x1a` (loop-iteration), not `0x01` (conditional skip).
//
// WHY A NEW CARRIER IS NEEDED, in the words of the experiment that declined the
// field yesterday. EXP-0184 swept all 256 values over TEN occurrences spanning
// nesting depth 1..3 with every detection-power control firing, and got 0/2560.
// Its own limitation section states the gap exactly:
//
//     "every one of the ten occurrences is `0f 05 54 01` ... none of our three
//      loop shapes (cf_loop, cf_loopif, cf_if1) emitted `if_push` at all, so the
//      loop-iteration region kind (scope_kind = 0x1a), which is where db.json's
//      0x54/0x56 nesting-parity claim actually comes from, was never reached.
//      The carriers span nesting DEPTH; they do not span REGION KIND."
//
// So the dimension this file adds is REGION KIND. EXP-0184's loop carriers put
// the trip count in a register expression of `t` (`n = (t & 3) + 1`) and the
// compiler lowered them without a push. Here every trip count is loaded FROM
// MEMORY, so it is opaque to the compiler, and the loops are NESTED -- the exact
// shape (L1/L2/L3 ladder) db.json's provenance names.
//
//   k_cf_nl2     two nested memory-bounded loops           loop-iter, depth 2
//   k_cf_nl3     three nested memory-bounded loops         loop-iter, depth 3
//   k_cf_nlif    if/else inside two nested loops           mixed kinds, depth 3
//   k_cf_wbrk    while(true)+break, nested twice           loop-iter via break
//   k_cf_ifnl    two nested loops inside an if/else        cond-skip then loop-iter
//   k_cf_lcont   nested loops with a `continue` edge       the continue-edge narrow
//
// DISPATCH GEOMETRY IS LOAD-BEARING (EXP-0179): an unconditional `if_push` with
// `scope_kind == 0x01` masks off the only lane of a ONE-THREAD dispatch in both
// mask banks. Every carrier here is grid 32 / threadgroup 32 and the observable
// is the whole 32-lane vector, so "the mask narrowed" and "the mask narrowed
// differently" stay distinguishable instead of collapsing to a dead dispatch.
//
// THE OBSERVABLE DOES NOT CO-VARY WITH THE FIELD (protocol 3a): `scope` selects a
// mask bank; the observable is 32 per-lane words at FIXED addresses that the
// field cannot name or relocate.
//
// ARITHMETIC IS INTEGER, DELIBERATELY. acc = acc*3 + 7 (mod 2^32) is bit-exact on
// the host for any iteration count, so the oracle needs no float reasoning, and
// every expected value is non-zero (Apple9's usual failure mode is a SILENT ZERO,
// and a zero oracle would score a silent zero as a pass).
//
// out[32] is an INTEGRITY SENTINEL stored BEFORE any divergent region is entered,
// so it survives even if every lane is later masked off. out[33..39] are never
// stored and must stay POISON.
#include <metal_stdlib>
using namespace metal;

#define SENT out[32] = 0x5A5A1234u;

// n[t]      -> outer trip count  (1..4)
// n[32 + t] -> inner trip count  (1..3)
// n[64 + t] -> third trip count  (1..2)

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
