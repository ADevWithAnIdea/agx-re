// RT-1b atomics + barrier kernels (OUR OWN MSL). Falsify atomic_rmw (0x67,
// op@byte+12), device vs threadgroup (byte+1 bit1), cmpxchg (0x24), and the
// threadgroup barrier (0x07 byte+3 mem-scope 0x61 tg / 0x85 dev).
#include <metal_stdlib>
using namespace metal;

// --- single-thread RMW to an initialized counter: out = op(c_init, in0).
// grid=1 removes contention so the op field at byte+12 is cleanly observable:
// splicing the op byte gives distinct outputs (add/sub/and/or/xor/xchg/min/max).
kernel void rmw1(device atomic_int* c [[buffer(0)]], device const int* in [[buffer(1)]],
                 device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[0] = atomic_fetch_add_explicit(c, in[0], memory_order_relaxed);
    o[1] = atomic_load_explicit(c, memory_order_relaxed);   // post-value
}

// --- compare-exchange (0x24) single thread.
kernel void cxchg(device atomic_int* c [[buffer(0)]], device const int* in [[buffer(1)]],
                  device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    int expected = in[1];
    bool ok = atomic_compare_exchange_weak_explicit(c, &expected, in[0],
                    memory_order_relaxed, memory_order_relaxed);
    o[0] = ok ? 1 : 0;      // did it swap?
    o[1] = expected;        // observed value
    o[2] = atomic_load_explicit(c, memory_order_relaxed);
}

// --- contended device add: grid threads each add 1 -> counter == grid.
kernel void agg(device atomic_int* c [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(c, 1, memory_order_relaxed);
}

// --- threadgroup atomic add (space byte+1 bit1): compare device vs tg encoding.
kernel void tgadd(device const int* in [[buffer(1)]], device int* o [[buffer(2)]],
                  threadgroup atomic_int* t [[threadgroup(0)]],
                  uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]]) {
    if (li == 0) atomic_store_explicit(t, 0, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(t, in[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (li == 0) o[i / 64] = atomic_load_explicit(t, memory_order_relaxed);
}

// --- barrier race: readers read a neighbour's tg slot; needs the tg barrier.
// Splicing the barrier byte+3 scope (0x61 -> 0x00) should surface stale reads.
kernel void race(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]],
                 uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup uint scratch[256];
    uint v = a[gid];
    uint d = v + 1u;
    for (uint i = 0; i < 200u; i++) { d = d * 1664525u + 1013904223u; }  // delay writers
    scratch[lid] = v + (d & 0u);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = scratch[255 - lid];   // cross-lane read: correct only with barrier
}
