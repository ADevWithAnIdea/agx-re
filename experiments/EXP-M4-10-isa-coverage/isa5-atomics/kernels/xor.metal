#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_int* g [[buffer(0)]],
              device const int* v [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    atomic_fetch_xor_explicit(&g[0], v[i], memory_order_relaxed);
}
