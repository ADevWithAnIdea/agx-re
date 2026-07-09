#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* in [[buffer(1)]], uint g [[thread_position_in_grid]], uint t [[thread_position_in_threadgroup]]){
  threadgroup atomic_float s;
  if(t==0) atomic_store_explicit(&s,0.0f,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  float r=atomic_fetch_add_explicit(&s, in[g], memory_order_relaxed); out[g]=r;
  threadgroup_barrier(mem_flags::mem_threadgroup);
  out[g]=atomic_load_explicit(&s, memory_order_relaxed);
}
