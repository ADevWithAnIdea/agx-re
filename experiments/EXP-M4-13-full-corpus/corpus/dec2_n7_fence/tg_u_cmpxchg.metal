#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device const uint* in [[buffer(1)]], uint g [[thread_position_in_grid]], uint t [[thread_position_in_threadgroup]]){
  threadgroup atomic_uint s;
  if(t==0) atomic_store_explicit(&s,0u,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  uint e=in[g]; bool ok=atomic_compare_exchange_weak_explicit(&s, &e, in[g]+1u, memory_order_relaxed, memory_order_relaxed); out[g]=ok?e:0u;
  threadgroup_barrier(mem_flags::mem_threadgroup);
  out[g]=atomic_load_explicit(&s, memory_order_relaxed);
}
