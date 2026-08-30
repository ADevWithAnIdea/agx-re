// EXP-0202 AMENDMENT (v3) -- shift_amt_move OPERAND-PROVENANCE carriers.
// AUTHORED BY US; OWN-SHADER. The v1/v2 kernel files are NOT edited: run02
// executed against their frozen hashes and must stay reproducible.
//
// WHY THIS FILE EXISTS. `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 6 makes
// REGISTER LIFECYCLE AND OPERAND PROVENANCE a required dimension:
//
//   "Repeat relevant fields with values produced by ALU, uniform/system input,
//    memory load, texture/interpolator, and other available producer classes.
//    Vary immediate use, intervening independent ALU, control-flow merge, and
//    overwrite. If behaviour depends on how or when a register was defined,
//    document the lifecycle rule and do not misattribute it to an encoding bit."
//
// `shift_amt_move.src_flag` is modelled as a SOURCE-CLASS selector, so this is
// exactly the dimension it would control. The v1 carriers covered only ONE
// producer class -- a device memory load -- because the compiler lowered the
// thread-invariant `constant uint&` amount through a GPR and emitted bytes
// IDENTICAL to the memory-load carrier (census: `0b011c05` in both).
//
//   k_sam_alu   amount produced by an ALU chain
//   k_sam_sys   amount produced by a SYSTEM VALUE (thread position -> get_sr)
//   k_sam_lane  amount produced by a SIMD lane id (a different system input)
//   k_sam_ovr   amount defined, then an intervening independent ALU op, then used
//               (register lifetime stretched across an unrelated definition)
//   k_sam_cf    amount defined on BOTH sides of a control-flow merge
//
// ORACLE: computed on the host from these exact inputs by the same arithmetic.
//   a[t] = 0x8000000B + t*0x01234567 ; no expected value is 0.
// SENTINEL out[8] = 12345, written first. POISON on buffer 0.
#include <metal_stdlib>
using namespace metal;

#define SENT out[8] = 12345u;

kernel void k_sam_alu(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint amt = (a[t] * 3u + 1u) & 31u;          // ALU-produced
    out[t] = rotate(a[t], amt);
}

kernel void k_sam_sys(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = rotate(a[t], (t * 3u + 1u) & 31u); // system-value-produced
}

kernel void k_sam_lane(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]],
                       uint l [[thread_index_in_simdgroup]]) {
    SENT
    out[t] = rotate(a[t], (l + 1u) & 31u);      // a different system input
}

kernel void k_sam_ovr(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint amt = b[t] & 31u;
    uint junk = a[t] ^ 0x5A5A5A5Au;             // intervening independent ALU
    junk = junk * 7u + 3u;
    out[t] = rotate(a[t], amt) ^ (junk & 1u);
}

kernel void k_sam_cf(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     uint t [[thread_position_in_grid]]) {
    SENT
    uint amt;
    if (b[t] & 1u) { amt = (b[t] * 2u) & 31u; } // defined on both sides of a
    else           { amt = (b[t] + 5u) & 31u; } // control-flow merge
    out[t] = rotate(a[t], amt);
}
