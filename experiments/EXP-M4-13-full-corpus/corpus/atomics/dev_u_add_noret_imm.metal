#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint* o [[buffer(0)]], device uint* out [[buffer(1)]], device const uint* in [[buffer(2)]], uint i [[thread_position_in_grid]]){
atomic_fetch_add_explicit(&o[i], 1u, memory_order_relaxed);
}
