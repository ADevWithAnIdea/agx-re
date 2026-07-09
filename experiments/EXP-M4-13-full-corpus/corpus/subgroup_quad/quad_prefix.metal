#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    uint v=a[i];
    o[i]    = quad_prefix_inclusive_sum(v);
    o[i+1u] = quad_prefix_exclusive_sum(v);
    o[i+2u] = quad_prefix_inclusive_product(v);
    o[i+3u] = quad_prefix_exclusive_product(v);
}
