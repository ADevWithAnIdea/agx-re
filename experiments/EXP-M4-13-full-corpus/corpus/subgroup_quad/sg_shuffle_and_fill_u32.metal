#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
              device const uint* f[[buffer(2)]], uint i[[thread_position_in_grid]]){
    uint v=a[i], fill=f[i];
    o[i]    = simd_shuffle_and_fill_up(v, fill, 2);
    o[i+1u] = simd_shuffle_and_fill_down(v, fill, 2);
}
