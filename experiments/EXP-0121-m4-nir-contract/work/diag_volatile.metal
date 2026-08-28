#include <metal_stdlib>
using namespace metal;

struct MB { uint payload[4]; atomic_uint ready; atomic_uint ack; };

// Variant A: local cast to volatile inside a helper function (matches opt1011_ordering.metal's load_P/store_P)
inline uint load_P_local(device atomic_uint *p) { return *(volatile device uint*)p; }
inline bool wait_P_local(device atomic_uint *p, uint want, uint bound) {
    for (uint s = 0; s < bound; ++s) if (load_P_local(p) == want) return true;
    return false;
}
kernel void diag_local_cast(volatile device MB *boxes [[buffer(0)]],
                             device atomic_uint *out [[buffer(1)]],
                             constant uint &bound [[buffer(2)]],
                             uint lid [[thread_position_in_threadgroup]],
                             uint tg [[threadgroup_position_in_grid]]) {
    if (lid != 0u) return;
    device MB *m = (device MB*)&boxes[0];
    if (tg == 0u) {
        // producer: write ready=1 after a short spin so consumer must actually wait
        for (uint s = 0; s < 5000u; ++s) { }
        *(device uint*)(&m->ready) = 1u;
    } else if (tg == 1u) {
        bool got = wait_P_local(&m->ready, 1u, bound);
        atomic_fetch_add_explicit(&out[0], got ? 1u : 0u, memory_order_relaxed);
    }
}

// Variant B: TOP-LEVEL volatile parameter, dereference directly (no helper-function cast)
kernel void diag_toplevel_volatile(volatile device MB *boxes [[buffer(0)]],
                                    device atomic_uint *out [[buffer(1)]],
                                    constant uint &bound [[buffer(2)]],
                                    uint lid [[thread_position_in_threadgroup]],
                                    uint tg [[threadgroup_position_in_grid]]) {
    if (lid != 0u) return;
    volatile device uint *readyp = (volatile device uint*)&boxes[0].ready;
    if (tg == 0u) {
        for (uint s = 0; s < 5000u; ++s) { }
        *readyp = 1u;   // direct volatile store through a top-level-volatile-derived pointer, no helper call
    } else if (tg == 1u) {
        bool got = false;
        for (uint s = 0; s < bound; ++s) {
            if (*readyp == 1u) { got = true; break; }  // direct volatile load, inline, no helper call
        }
        atomic_fetch_add_explicit(&out[0], got ? 1u : 0u, memory_order_relaxed);
    }
}
