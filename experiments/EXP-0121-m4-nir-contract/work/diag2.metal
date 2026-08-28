#include <metal_stdlib>
using namespace metal;
struct MB { uint payload[4]; atomic_uint ready; atomic_uint ack; };

kernel void diag_post_spin_read(volatile device MB *boxes [[buffer(0)]],
                                 device atomic_uint *out [[buffer(1)]],
                                 constant uint &bound [[buffer(2)]],
                                 uint lid [[thread_position_in_threadgroup]],
                                 uint tg [[threadgroup_position_in_grid]]) {
    if (lid != 0u) return;
    volatile device uint *readyp = (volatile device uint*)&boxes[0].ready;
    if (tg == 0u) {
        // producer: busy-spin a FIXED amount then write (deterministic delay), then
        // ALSO write a distinct "producer done" flag so the consumer's post-spin
        // check has a ground truth for "producer definitely already wrote ready".
        for (uint s = 0; s < 200000u; ++s) { }
        *readyp = 1u;
        atomic_fetch_add_explicit(&out[2], 1u, memory_order_relaxed);  // out[2] = producer completed marker
    } else if (tg == 1u) {
        bool got_in_loop = false;
        for (uint s = 0; s < bound; ++s) {
            if (*readyp == 1u) { got_in_loop = true; break; }
        }
        atomic_fetch_add_explicit(&out[0], got_in_loop ? 1u : 0u, memory_order_relaxed);  // out[0]: seen IN loop
        // extra delay AFTER the loop gives the producer plenty of extra wall-clock
        // time to have definitely completed its write by now, regardless of the loop
        // outcome, then take ONE fresh read:
        for (uint s = 0; s < 2000000u; ++s) { }
        uint post = *readyp;
        atomic_fetch_add_explicit(&out[1], post, memory_order_relaxed);  // out[1]: fresh post-spin read value
    }
}
