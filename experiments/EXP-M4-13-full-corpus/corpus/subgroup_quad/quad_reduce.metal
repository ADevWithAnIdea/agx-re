#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    uint v=a[i];
    o[i]    = quad_sum(v);
    o[i+1u] = quad_product(v);
    o[i+2u] = quad_min(v);
    o[i+3u] = quad_max(v);
    o[i+4u] = quad_and(v);
    o[i+5u] = quad_or(v);
    o[i+6u] = quad_xor(v);
}
