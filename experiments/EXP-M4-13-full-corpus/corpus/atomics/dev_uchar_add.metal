#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uchar* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ atomic_fetch_add_explicit(&o[i], (uchar)1, memory_order_relaxed); }
