#include <metal_stdlib>
using namespace metal;
// ATOM-07/ATOM-08 device-memory-fence litmus, generalizing EXP-0051's
// msg_cross_relaxed/msg_cross_fence_device mailbox pattern from ONE
// producer/consumer threadgroup pair to PAIRS_MAX independent pairs dispatched
// in a single compute command, to maximize the chance a given pair's producer
// and consumer land on physically different GPU cores. threadgroup (2k) is the
// producer for mailbox k, threadgroup (2k+1) is the consumer; only lane 0 of
// each threadgroup participates. Four ordering variants matrix producer/
// consumer fencing independently (RR=both relaxed, FR/RF=asymmetric,
// FF=both fenced) -- OUR OWN MSL, reusing EXP-0051's asymmetric() payload
// generator and bounded wait_value() spin (never an unbounded loop: a timeout
// is recorded as data, not a hang).

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

// Bounded spin -- NEVER an unbounded loop. A timeout is recorded as data.
inline bool wait_value(device atomic_uint *p, uint want, uint bound) {
    for (uint spin = 0; spin < bound; ++spin)
        if (atomic_load_explicit(p, memory_order_relaxed) == want) return true;
    return false;
}

// out layout: out[0]=mismatch count, out[1]=producer timeouts, out[2]=consumer
// timeouts, out[3]=messages completed (consumer side).
inline void run_pair(device Mailbox *boxes, device atomic_uint *out,
                     uint iterations, uint spinBound, uint lid, uint tg,
                     bool producerFenced, bool consumerFenced) {
    if (lid != 0u) return;
    uint pair = tg / 2u;
    device Mailbox *m = &boxes[pair];
    uint salt = pair * 53u + 7u;
    if ((tg & 1u) == 0u) {
        // producer
        for (uint i = 1u; i <= iterations; ++i) {
            if (!wait_value(&m->ack, i - 1u, spinBound)) {
                atomic_fetch_add_explicit(&out[1], 1u, memory_order_relaxed);
                return;
            }
            payload_write(m, i, salt);
            if (producerFenced)
                atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device);
            atomic_store_explicit(&m->ready, i, memory_order_relaxed);
        }
    } else {
        // consumer
        uint bad = 0u, done = 0u;
        for (uint i = 1u; i <= iterations; ++i) {
            if (!wait_value(&m->ready, i, spinBound)) {
                atomic_fetch_add_explicit(&out[2], 1u, memory_order_relaxed);
                break;
            }
            if (consumerFenced)
                atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst, thread_scope_device);
            bad += payload_mismatch(m, i, salt);
            atomic_store_explicit(&m->ack, i, memory_order_relaxed);
            ++done;
        }
        atomic_fetch_add_explicit(&out[0], bad, memory_order_relaxed);
        atomic_fetch_add_explicit(&out[3], done, memory_order_relaxed);
    }
}

kernel void msg_pairs_RR(device Mailbox *boxes [[buffer(0)]],
                         device atomic_uint *out [[buffer(1)]],
                         constant uint &iterations [[buffer(2)]],
                         constant uint &spinBound [[buffer(3)]],
                         uint lid [[thread_position_in_threadgroup]],
                         uint tg [[threadgroup_position_in_grid]]) {
    run_pair(boxes, out, iterations, spinBound, lid, tg, false, false);
}

kernel void msg_pairs_FR(device Mailbox *boxes [[buffer(0)]],
                         device atomic_uint *out [[buffer(1)]],
                         constant uint &iterations [[buffer(2)]],
                         constant uint &spinBound [[buffer(3)]],
                         uint lid [[thread_position_in_threadgroup]],
                         uint tg [[threadgroup_position_in_grid]]) {
    run_pair(boxes, out, iterations, spinBound, lid, tg, true, false);
}

kernel void msg_pairs_RF(device Mailbox *boxes [[buffer(0)]],
                         device atomic_uint *out [[buffer(1)]],
                         constant uint &iterations [[buffer(2)]],
                         constant uint &spinBound [[buffer(3)]],
                         uint lid [[thread_position_in_threadgroup]],
                         uint tg [[threadgroup_position_in_grid]]) {
    run_pair(boxes, out, iterations, spinBound, lid, tg, false, true);
}

kernel void msg_pairs_FF(device Mailbox *boxes [[buffer(0)]],
                         device atomic_uint *out [[buffer(1)]],
                         constant uint &iterations [[buffer(2)]],
                         constant uint &spinBound [[buffer(3)]],
                         uint lid [[thread_position_in_threadgroup]],
                         uint tg [[threadgroup_position_in_grid]]) {
    run_pair(boxes, out, iterations, spinBound, lid, tg, true, true);
}
