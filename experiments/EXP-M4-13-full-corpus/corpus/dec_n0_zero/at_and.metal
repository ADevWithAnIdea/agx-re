#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint* p [[buffer(0)]], uint gid [[thread_position_in_grid]]){
    atomic_fetch_and_explicit(p, 7u, memory_order_relaxed);
}
