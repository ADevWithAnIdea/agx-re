#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic<double>* o [[buffer(0)]], device const float* a [[buffer(1)]]) {
  atomic_store_explicit(o, (double)a[0], memory_order_relaxed); }
