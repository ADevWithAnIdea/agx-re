#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_float* g [[buffer(0)]],
              device const float* v [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&g[0], v[i], memory_order_relaxed);
}
