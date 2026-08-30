// EXP-0184 divergent-control-flow carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET FIELD: `if_push.scope` = byte+2 of the 4-byte `0f 05 <scope> <kind>`.
// db.json: "selects the reconvergence MASK BANK -- it ping-pongs 0x54/0x56 with
// NESTING PARITY (outer even = 0x54, nested odd = 0x56)".
//
// WHY THE PRIOR ARM COULD NOT SEE IT. EXP-0140 swept all 256 values on ONE
// carrier and nothing moved; EXP-0164 withheld the field. The dimension the
// field is modelled to control is NESTING PARITY, and no prior arm ever varied
// nesting depth: every carrier was one region deep, so the two documented bank
// values were structurally interchangeable BY CONSTRUCTION. That is the
// `iter_at.loc` failure (EXP-0164: eight carriers at samples=1 are one carrier)
// and the `get_sr.form` result (declined on eight arms, live on the ninth --
// the one that changed stage).
//
// The ladder below therefore spans nesting depth 1, 2 and 3 and BOTH region
// kinds db.json names (`scope_kind` 0x01 conditional-skip and 0x1a loop-iter):
//
//   k_cf_if1     one if/else                       depth 1, cond-skip
//   k_cf_if2     if/else inside if/else            depth 2, cond-skip
//   k_cf_if3     three levels of if/else           depth 3, cond-skip
//   k_cf_loop    data-dependent for loop           depth 1, loop-iter
//   k_cf_loopif  if/else inside a loop             depth 2, mixed kinds
//
// DISPATCH GEOMETRY IS LOAD-BEARING (EXP-0179). An unconditional `if_push` with
// `scope_kind == 0x01` masks off the only lane of a ONE-THREAD dispatch, in
// BOTH mask banks, which killed a frozen carrier there. Every carrier here runs
// **grid 32 / threadgroup 32** and the observable is the WHOLE 32-lane vector,
// so "the mask narrowed" and "the mask narrowed differently" are distinguishable
// instead of both collapsing to a dead dispatch.
//
// THE OBSERVABLE DOES NOT CO-VARY WITH THE FIELD (protocol 3a). `scope` selects
// a mask bank; the observable is 32 per-lane result words at FIXED addresses,
// none of which the field can name or relocate.
//
// out[32] is an INTEGRITY SENTINEL stored BEFORE any divergent region is
// entered, so it is written even if every lane is later masked off; out[33..39]
// are never stored to and must stay POISON.
//
// ORACLE: exact, host-computed from this source. a[t] = 3.0 + t (t = 0..31), and
// every operation is *2, *4, +k on small integers, so every expected value is
// exact in binary32 and non-zero.
#include <metal_stdlib>
using namespace metal;

#define SENT32 out[32] = 7.5f;

kernel void k_cf_if1(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT32
    float v = a[t];
    if ((t & 1u) != 0u) { out[t] = v * 2.0f + 1.0f; }
    else                { out[t] = v + 100.0f; }
}

kernel void k_cf_if2(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT32
    float v = a[t];
    if ((t & 1u) != 0u) {
        if ((t & 2u) != 0u) { out[t] = v * 2.0f + 1.0f; }
        else                { out[t] = v + 100.0f; }
    } else {
        if ((t & 2u) != 0u) { out[t] = v * 4.0f + 2.0f; }
        else                { out[t] = v + 200.0f; }
    }
}

kernel void k_cf_if3(device float *out [[buffer(0)]],
                     device const float *a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    SENT32
    float v = a[t];
    if ((t & 1u) != 0u) {
        if ((t & 2u) != 0u) {
            if ((t & 4u) != 0u) { out[t] = v * 2.0f + 1.0f; }
            else                { out[t] = v + 100.0f; }
        } else {
            if ((t & 4u) != 0u) { out[t] = v * 4.0f + 2.0f; }
            else                { out[t] = v + 200.0f; }
        }
    } else {
        if ((t & 2u) != 0u) {
            if ((t & 4u) != 0u) { out[t] = v * 8.0f + 3.0f; }
            else                { out[t] = v + 300.0f; }
        } else {
            if ((t & 4u) != 0u) { out[t] = v * 16.0f + 4.0f; }
            else                { out[t] = v + 400.0f; }
        }
    }
}

kernel void k_cf_loop(device float *out [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT32
    float v = a[t];
    uint n = (t & 3u) + 1u;                 // data-dependent trip count
    for (uint i = 0u; i < n; i++) { v = v * 2.0f + 1.0f; }
    out[t] = v;
}

kernel void k_cf_loopif(device float *out [[buffer(0)]],
                        device const float *a [[buffer(1)]],
                        uint t [[thread_position_in_grid]]) {
    SENT32
    float v = a[t];
    uint n = (t & 3u) + 1u;
    for (uint i = 0u; i < n; i++) {
        if (((t >> i) & 1u) != 0u) { v = v * 2.0f; }
        else                       { v = v + 10.0f; }
    }
    out[t] = v;
}
