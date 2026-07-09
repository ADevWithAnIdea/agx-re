#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* in [[buffer(1)]], uint g [[thread_position_in_grid]], uint t [[thread_position_in_threadgroup]]){
  threadgroup atomic_int s;
  if(t==0) atomic_store_explicit(&s,0,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  int r=atomic_fetch_min_explicit(&s, (int)in[g], memory_order_relaxed); out[g]=(int)r;
  threadgroup_barrier(mem_flags::mem_threadgroup);
  out[g]=(int)atomic_load_explicit(&s, memory_order_relaxed);
}
