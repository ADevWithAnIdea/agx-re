#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
              device const uint* d[[buffer(2)]], uint i[[thread_position_in_grid]]){
    uint v=a[i];
    ushort delta=(ushort)(d[i] & 31u);
    o[i]    = simd_shuffle_up(v, delta);
    o[i+1u] = simd_shuffle_down(v, delta);
}
