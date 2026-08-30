// EXP-0206 CALL/RETURN carriers -- THE MEMORY/EXECUTION-ORDERING DIMENSION and
// THE LEAF-vs-NON-LEAF LINK DIMENSION. AUTHORED BY US (OWN-SHADER).
//
// TARGET FIELDS carried here:
//   `call.tail`          byte+13 of the 14-byte direct call
//   `ret.scoreboard`     byte+3 of `8f <linkmode> 54 <scoreboard>`
//   `ret_luse.linkmode`  byte+1 of `8f <linkmode> 56 <tail>`
//   `stop.reserved`      bits 8..31 of `0e <r24>` -- BOTH the final stop and any
//                        MID-PROGRAM stop that separates the main body from an
//                        out-of-line callee
//
// ------------------------------------------------------------------ WHY THESE
//
// (1) `ret.scoreboard` was DECLINED, as pre-registered, by EXP-0179: "the
//     dimension it controls is memory/execution ORDERING, and neither carrier
//     differs in that dimension -- both return from a leaf callee with no
//     outstanding asynchronous operation to wait on. Zero movement here means
//     'this carrier cannot ask the question', not 'the field is inert'."
//     So this file spans that dimension explicitly, from NOTHING TO WAIT ON to
//     AN ATOMIC READ-MODIFY-WRITE WHOSE RESULT IS CONSUMED AFTER THE RETURN:
//
//       k_cl_pure      callee is pure arithmetic; no memory op anywhere near
//                      the call.                       <-- the ordering NEGATIVE
//       k_cl_ldret     the callee itself issues the device LOAD and returns it.
//       k_cl_ldacross  the CALLER issues a device load, then calls; the load's
//                      result is consumed only AFTER the return, so the load may
//                      still be in flight at the `ret`.
//       k_cl_stacross  the CALLER issues a device STORE, then calls, then READS
//                      THAT LOCATION BACK -- a store->load hazard that spans the
//                      return.
//       k_cl_atomic    the callee performs an atomic fetch-add on the output
//                      buffer and returns the OLD value, which the caller then
//                      uses.                          <-- the strongest hazard
//
//     These five differ in exactly one axis: how much unretired memory traffic
//     exists at the moment the `ret` executes.
//
// (2) `ret_luse.linkmode` was WITHDRAWN because it had ONE distinct valid
//     payload across 32 legal values -- the values ran legally and were
//     INDISTINGUISHABLE, which is a hazard map, not a semantic. db.json models
//     byte+1 as leaf (0x02) vs non-leaf-restore-link (0x12) vs cf-merge
//     (0x04/0x05). A LEAF-ONLY carrier cannot tell those apart, because there is
//     no saved link to restore. So this file supplies NON-LEAF frames:
//
//       k_cl_leaf      one out-of-line leaf callee.     <-- the link NEGATIVE
//       k_cl_chain     a non-leaf mid that calls two leaves.
//       k_cl_deep      three call levels -> two nested non-leaf frames.
//       k_cl_spill     a non-leaf frame with heavy live state across its call.
//
//     At a NON-LEAF return, substituting the leaf link mode should fail to
//     restore the link and return somewhere else -- a DIFFERENT VALID PAYLOAD,
//     which is precisely the observation the withdrawal says is missing.
//
// (3) `call.tail` was WITHHELD because the gate that promoted it had no
//     `moved >= 1` conjunct -- a perfectly inert field passed it. It may well be
//     inert. Here it is swept densely on carriers spanning both dimensions above,
//     against a gate that requires actual movement, with `call.b6` (bit 1 proven
//     load-bearing by EXP-0179 arm S) as the detection-power control.
//
// (4) `stop.reserved`. EXP-0003/EXP-0010 corrupted the FINAL stop word and saw a
//     no-op, which is why "the true end of program is the out-of-band metadata
//     code length". That says nothing about a MID-PROGRAM stop. In a kernel with
//     an out-of-line callee the callee is placed AFTER the main body's stop, so
//     that stop must actually stop -- otherwise execution falls through into the
//     callee. Every carrier in this file therefore contains a mid-program stop,
//     and that is where a POSITIVE CONTROL IN THE TERMINATION DIMENSION becomes
//     available (see PRE_REGISTRATION.md H6).
//
// ------------------------------------------------------------------ INVARIANTS
//
// out[32] is an INTEGRITY SENTINEL, stored FIRST, through a path independent of
// every instruction under test. out[33..39] are never stored and must read back
// as their own POISON. The observable is 32 per-lane words at FIXED addresses --
// no value of any field under test can name or relocate them, so the observable
// does not co-vary with the field (FIELD-SWEEP-PROTOCOL 3a).
//
// All arithmetic is integer and bit-exact on the host, so every oracle is
// computed by simulating OUR OWN MSL, never read back from the GPU. Every
// expected value is asserted non-zero and distinct from its poison word.
//
// Structure (not values, not oracles) cited from EXP-0179 kernels/census/
// c_frame.metal and c_noinline.metal, which established that
// `__attribute__((noinline))` is the spelling that yields an out-of-line call on
// this toolchain.
#include <metal_stdlib>
using namespace metal;

#define SENT out[32] = 0x5A5A1234u;

// ------------------------------------------------------------- shared callees
// Deliberately non-trivial and called from more than one kernel, so the compiler
// has no incentive to clone-and-inline them despite the attribute.

__attribute__((noinline))
static uint pf(uint i) { return i * i * 5u + i * 3u + 13u; }

__attribute__((noinline))
static uint lf_add(uint a, uint b) { return a * 3u + b + 7u; }

__attribute__((noinline))
static uint lf_mul(uint a, uint b) { return a * 5u + b * 2u + 11u; }

// ---------------------------------------------------- (2) LINK-DIMENSION set

// L1 LEAF: exactly one out-of-line call, to a leaf. The ordering negative for
// the link dimension: there is no saved link to restore.
kernel void k_cl_leaf(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = lf_add(a[t], t + 1u);
}

// L2 NON-LEAF: a mid function that itself calls two leaves.
__attribute__((noinline))
static uint c_mid(uint a, uint b) { return lf_add(a, b) ^ lf_mul(b, a); }
kernel void k_cl_chain(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = c_mid(a[t], t + 1u);
}

// L3 THREE LEVELS: two nested non-leaf frames.
__attribute__((noinline))
static uint d_mid(uint a, uint b) { return lf_add(a, b) * 2u + 5u; }
__attribute__((noinline))
static uint d_out(uint a, uint b) { return d_mid(a, b) + lf_mul(a, b); }
kernel void k_cl_deep(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = d_out(a[t], t + 1u);
}

// L4 SPILLING non-leaf frame: twelve values live across the inner call.
__attribute__((noinline))
static uint s_big(uint a, uint b) {
    uint t0=a*11u,t1=a*13u,t2=a*17u,t3=a*19u,t4=a*23u,t5=a*29u;
    uint u0=b*31u,u1=b*37u,u2=b*41u,u3=b*43u,u4=b*47u,u5=b*53u;
    uint s = lf_add(a, b);
    return s + t0+t1+t2+t3+t4+t5 + u0+u1+u2+u3+u4+u5;
}
kernel void k_cl_spill(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = s_big(a[t], t + 1u);
}

// ------------------------------------------------ (1) ORDERING-DIMENSION set

// O0 PURE: nothing to wait on at the return. The ordering NEGATIVE control.
kernel void k_cl_pure(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    SENT
    uint y = pf(t + 1u);
    out[t] = y * 3u + (t + 1u) * 7u + 9u;
}

// O1 LOAD IN CALLEE: the callee issues the device load and returns its value, so
// the load must have retired before the return delivers a usable register.
__attribute__((noinline))
static uint m_ld(device const uint *p, uint i) { return p[i] * 3u + 7u; }
kernel void k_cl_ldret(device uint *out [[buffer(0)]],
                       device const uint *a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) {
    SENT
    out[t] = m_ld(a, t) + (t + 1u);
}

// O2 LOAD ACROSS THE CALL: the caller issues the load, then calls; the loaded
// value is consumed only after the return, so the load may still be in flight
// when the `ret` executes.
kernel void k_cl_ldacross(device uint *out [[buffer(0)]],
                          device const uint *a [[buffer(1)]],
                          uint t [[thread_position_in_grid]]) {
    SENT
    uint x = a[t];
    uint y = pf(t + 1u);
    out[t] = x * 3u + y + 7u;
}

// O3 STORE->LOAD ACROSS THE CALL: the caller stores, calls, then reads the same
// location back. The hazard the store must be ordered against spans the return.
kernel void k_cl_stacross(device uint *out [[buffer(0)]],
                          device const uint *a [[buffer(1)]],
                          uint t [[thread_position_in_grid]]) {
    SENT
    uint v = a[t] * 3u + 7u;
    out[t] = v;
    uint y = pf(t + 1u);
    out[t] = out[t] ^ (y * 2u);
}

// O4 ATOMIC RMW IN THE CALLEE, result consumed after the return. The old value
// is the buffer's POISON word, so the oracle proves the atomic really executed
// against the pre-filled buffer and not against a zeroed one.
__attribute__((noinline))
static uint m_at(device atomic_uint *o, uint i, uint v) {
    return atomic_fetch_add_explicit(&o[i], v, memory_order_relaxed);
}
kernel void k_cl_atomic(device atomic_uint *out [[buffer(0)]],
                        device const uint *a [[buffer(1)]],
                        uint t [[thread_position_in_grid]]) {
    atomic_store_explicit(&out[32], 0x5A5A1234u, memory_order_relaxed);
    uint old = m_at(out, t, a[t]);
    atomic_store_explicit(&out[t], old ^ (a[t] * 3u + 7u), memory_order_relaxed);
}
