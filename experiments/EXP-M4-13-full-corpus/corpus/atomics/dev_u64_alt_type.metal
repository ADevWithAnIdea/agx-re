#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint64_t* o [[buffer(0)]], device ulong* out [[buffer(1)]], device const ulong* in [[buffer(2)]], uint i [[thread_position_in_grid]]){ out[i]=atomic_fetch_add_explicit(&o[i], in[i], memory_order_relaxed); }
