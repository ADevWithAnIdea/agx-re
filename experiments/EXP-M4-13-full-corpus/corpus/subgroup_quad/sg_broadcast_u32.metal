#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    uint v=a[i];
    o[i]    = simd_broadcast(v, 3);            // constant lane
    o[i+1u] = simd_broadcast_first(v);         // special broadcast form
}
