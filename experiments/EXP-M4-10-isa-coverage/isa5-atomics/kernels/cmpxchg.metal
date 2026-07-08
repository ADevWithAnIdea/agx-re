#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_int* g [[buffer(0)]],
              device const int* v [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    int expected = v[i];
    atomic_compare_exchange_weak_explicit(&g[0], &expected, 999,
        memory_order_relaxed, memory_order_relaxed);
}
