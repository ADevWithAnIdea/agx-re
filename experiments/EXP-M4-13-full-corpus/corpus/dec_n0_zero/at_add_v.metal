#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint* p [[buffer(0)]], device uint* v [[buffer(1)]], uint gid [[thread_position_in_grid]]){
    atomic_fetch_add_explicit(p, v[gid], memory_order_relaxed);
}
