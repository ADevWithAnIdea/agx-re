#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic<float>* p [[buffer(0)]], uint g [[thread_position_in_grid]]){
    atomic_fetch_add_explicit(p, 2.5f, memory_order_relaxed);
}
