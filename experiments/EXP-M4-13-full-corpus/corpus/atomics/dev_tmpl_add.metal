#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic<uint>* o [[buffer(0)]], device uint* out [[buffer(1)]], device const uint* in [[buffer(2)]], uint i [[thread_position_in_grid]]){ out[i]=atomic_fetch_add_explicit(&o[i], in[i], memory_order_relaxed); }
