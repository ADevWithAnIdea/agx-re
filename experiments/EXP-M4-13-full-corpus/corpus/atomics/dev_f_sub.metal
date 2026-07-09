#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_float* o [[buffer(0)]], device float* out [[buffer(1)]], device const float* in [[buffer(2)]], uint i [[thread_position_in_grid]]){
out[i]=atomic_fetch_sub_explicit(&o[i], in[i], memory_order_relaxed);
}
