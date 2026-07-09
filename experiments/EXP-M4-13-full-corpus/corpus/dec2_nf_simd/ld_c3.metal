#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], device const float* a2[[buffer(2)]], uint i[[thread_position_in_grid]]){
    float v=a[i];
    o[i]=ldexp(v,3);
}
