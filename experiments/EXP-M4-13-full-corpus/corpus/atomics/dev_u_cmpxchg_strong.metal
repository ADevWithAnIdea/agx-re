#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint* o [[buffer(0)]], device uint* out [[buffer(1)]], device const uint* in [[buffer(2)]], uint i [[thread_position_in_grid]]){
uint e=in[i]; bool ok=atomic_compare_exchange_strong_explicit(&o[i], &e, in[i]+1u, memory_order_relaxed, memory_order_relaxed); out[i]=ok?e:0u;
}
