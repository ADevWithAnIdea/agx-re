#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_float* o [[buffer(0)]], device float* out [[buffer(1)]], device const float* in [[buffer(2)]], uint i [[thread_position_in_grid]]){
float e=in[i]; bool ok=atomic_compare_exchange_weak_explicit(&o[i], &e, in[i]+1.0f, memory_order_relaxed, memory_order_relaxed); out[i]=ok?e:0.0f;
}
