#include <metal_stdlib>
using namespace metal;
// OPT-10/OPT-11: does an ORDINARY aligned Apple9 load (OPT-10) / store (OPT-11) satisfy
// atomic-load/store ordering & visibility when surrounded by the appropriate fences? Design
// mirrors EXP-0093's `litmus_devfence_pairs.metal` (own prior committed code; pattern reuse
// per SUBAGENT_BRIEF.md), which proved PAIRS>=4 producer/consumer threadgroup pairs expose
// real cross-core reordering and that SYMMETRIC atomic_thread_fence(mem_device,...) around
// FULLY ATOMIC ready/ack flags gives zero mismatches at every tested scale, while any
// unfenced or asymmetric-fenced configuration breaks.
//
// This kernel keeps the SAME underlying storage (an `atomic_uint` -- the stricter of the two
// access methods) for ready/ack, but accesses it FOUR different ways per kernel variant, to
// separate the store side (OPT-11) from the load side (OPT-10) without any storage-layout
// confound:
//   AA -- atomic store, atomic load    (baseline correctness sanity)
//   PA -- PLAIN (volatile, non-atomic) store, ATOMIC load   -> isolates OPT-11 (store)
//   AP -- ATOMIC store, PLAIN (volatile, non-atomic) load   -> isolates OPT-10 (load)
//   PP -- plain store, plain load                            -> combined real-world case
// "Plain" access is a raw dereference through a (volatile device uint*) reinterpretation of
// the SAME atomic_uint storage -- same bits, same alignment (4-byte, natively aligned),
// different access method. `volatile` only defeats compiler register-caching of the spin-wait
// load; it makes no claim about hardware ordering (see PRE_REGISTRATION.md's confounders note)
// -- the `atomic_thread_fence` calls are the mechanism actually under test.
//
// Each variant is built in both a FENCED (both sides call atomic_thread_fence(mem_device,
// seq_cst, thread_scope_device) at the same program points EXP-0093 validated) and an
// UNFENCED (deliberately-weak control, expected to break at PAIRS>=4) form -- 8 kernel
// functions total. Payload (the actual message data) is always a PLAIN (non-atomic) word
// array in every variant, exactly as in EXP-0093 -- OPT-10/11 concern the SIGNALING words
// themselves, not the payload.

inline uint asymmetric(uint epoch, uint index) {
    uint x = 0x9e3779b9u * (index + 1u) + 0x85ebca6bu * (epoch + 3u);
    return (x ^ (x >> 13) ^ 0xa5c31f27u) + (index << 16);
}

struct Mailbox {
    uint payload[4];
    atomic_uint ready;
    atomic_uint ack;
};

inline void payload_write(device Mailbox *m, uint iteration, uint salt) {
    m->payload[0] = asymmetric(iteration, salt + 0u);
    m->payload[1] = asymmetric(iteration, salt + 7u);
    m->payload[2] = asymmetric(iteration, salt + 19u);
    m->payload[3] = asymmetric(iteration, salt + 41u);
}
inline uint payload_mismatch(device Mailbox *m, uint iteration, uint salt) {
    uint n = 0;
    n += m->payload[0] != asymmetric(iteration, salt + 0u);
    n += m->payload[1] != asymmetric(iteration, salt + 7u);
    n += m->payload[2] != asymmetric(iteration, salt + 19u);
    n += m->payload[3] != asymmetric(iteration, salt + 41u);
    return n;
}

// ---- access-method primitives -------------------------------------------------------------
inline uint load_A(device atomic_uint *p) { return atomic_load_explicit(p, memory_order_relaxed); }
inline void store_A(device atomic_uint *p, uint v) { atomic_store_explicit(p, v, memory_order_relaxed); }
inline uint load_P(device atomic_uint *p) { return *(volatile device uint*)p; }
inline void store_P(device atomic_uint *p, uint v) { *(volatile device uint*)p = v; }

inline bool wait_A(device atomic_uint *p, uint want, uint bound) {
    for (uint s = 0; s < bound; ++s) if (load_A(p) == want) return true;
    return false;
}
inline bool wait_P(device atomic_uint *p, uint want, uint bound) {
    for (uint s = 0; s < bound; ++s) if (load_P(p) == want) return true;
    return false;
}

inline void fence_dev() {
    atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device);
}

// method: 0=AA 1=PA(store plain,load atomic) 2=AP(store atomic,load plain) 3=PP
inline void run_pair(device Mailbox *boxes, device atomic_uint *out,
                      uint iterations, uint spinBound, uint lid, uint tg,
                      int method, bool fenced) {
    if (lid != 0u) return;
    uint pair = tg / 2u;
    device Mailbox *m = &boxes[pair];
    uint salt = pair * 53u + 7u;
    bool storePlain = (method == 1 || method == 3);
    bool loadPlain  = (method == 2 || method == 3);
    if ((tg & 1u) == 0u) {
        // producer: wait for ack==i-1 (its own load method mirrors AA for simplicity -- the
        // ack side always uses the SAME method as this producer's "load" role would use on the
        // opposite mailbox in a symmetric protocol; kept atomic here so a stuck spin can never
        // be attributed to the *ack* path, isolating all divergence to the *ready* path this
        // function's `method`/`storePlain` controls).
        for (uint i = 1u; i <= iterations; ++i) {
            if (!wait_A(&m->ack, i - 1u, spinBound)) {
                atomic_fetch_add_explicit(&out[1], 1u, memory_order_relaxed);
                return;
            }
            payload_write(m, i, salt);
            if (fenced) fence_dev();
            if (storePlain) store_P(&m->ready, i); else store_A(&m->ready, i);
        }
    } else {
        // consumer
        uint bad = 0u, done = 0u;
        for (uint i = 1u; i <= iterations; ++i) {
            bool got = loadPlain ? wait_P(&m->ready, i, spinBound) : wait_A(&m->ready, i, spinBound);
            if (!got) {
                atomic_fetch_add_explicit(&out[2], 1u, memory_order_relaxed);
                break;
            }
            if (fenced) fence_dev();
            bad += payload_mismatch(m, i, salt);
            store_A(&m->ack, i);   // ack path fixed atomic (see producer-side note)
            ++done;
        }
        atomic_fetch_add_explicit(&out[0], bad, memory_order_relaxed);
        atomic_fetch_add_explicit(&out[3], done, memory_order_relaxed);
    }
}

#define MAKE(NAME, METHOD, FENCED) \
kernel void msg_##NAME(device Mailbox *boxes [[buffer(0)]], device atomic_uint *out [[buffer(1)]], \
                        constant uint &iterations [[buffer(2)]], constant uint &spinBound [[buffer(3)]], \
                        uint lid [[thread_position_in_threadgroup]], uint tg [[threadgroup_position_in_grid]]) { \
    run_pair(boxes, out, iterations, spinBound, lid, tg, METHOD, FENCED); \
}

MAKE(AA_fenced,   0, true)
MAKE(AA_unfenced, 0, false)
MAKE(PA_fenced,   1, true)
MAKE(PA_unfenced, 1, false)
MAKE(AP_fenced,   2, true)
MAKE(AP_unfenced, 2, false)
MAKE(PP_fenced,   3, true)
MAKE(PP_unfenced, 3, false)
