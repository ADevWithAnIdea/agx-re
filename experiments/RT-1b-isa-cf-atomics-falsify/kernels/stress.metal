// RT-1b stress kernel (OUR OWN MSL): deep control flow + a noinline call +
// device & threadgroup atomics + high register pressure (spill). Used to
// tokenize the whole _agc.main (census: should be ~0 leftover) and to confirm
// semantics against a CPU reference.
#include <metal_stdlib>
using namespace metal;

__attribute__((noinline)) static int mix(int a, int b) {
    int r = a; for (int k = 0; k < 8; k++) { r = r * 3 + b - (r >> 1); r ^= (b << (k & 3)); }
    return r;
}

kernel void big(device const int* a [[buffer(0)]],
                device int* out      [[buffer(1)]],
                device atomic_int* counter [[buffer(2)]],
                threadgroup atomic_int* tg [[threadgroup(0)]],
                uint gid [[thread_position_in_grid]],
                uint lid [[thread_position_in_threadgroup]]) {
    if (lid == 0) atomic_store_explicit(tg, 0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);

    int x = a[gid];
    // high register pressure: 24 simultaneously-live accumulators.
    int r[24];
    for (int k = 0; k < 24; k++) r[k] = x + k * 7 - (k & 5);
    for (int it = 0; it < 3; it++)
        for (int k = 0; k < 24; k++)
            r[k] = r[k] + r[(k + 1) % 24] - (r[(k + 7) % 24] >> 1) + (it * k);

    // deep data-dependent control flow
    int s = 0;
    for (int i = 0; i < (x & 15); i++) {
        if ((i & 1) == 0) { if (i < 4) s += r[i]; else s -= r[i & 23]; }
        else              { s ^= (r[(i * 3) & 23] << 1); }
        if (s > 100000) break;
    }
    s += mix(x, r[5]);                                  // call
    atomic_fetch_add_explicit(tg, s & 1, memory_order_relaxed);
    atomic_fetch_add_explicit(counter, 1, memory_order_relaxed);   // device atomic

    int acc = 0; for (int k = 0; k < 24; k++) acc += r[k];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = acc + s + atomic_load_explicit(tg, memory_order_relaxed);
}
