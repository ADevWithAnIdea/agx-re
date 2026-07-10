#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    uint v=a[i]; uint x=simd_shuffle(v,3u); uint y=simd_shuffle(v,5u); o[i]=x*y;
}
