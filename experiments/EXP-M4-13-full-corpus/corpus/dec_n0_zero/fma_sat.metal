#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const float* a [[buffer(1)]], uint g [[thread_position_in_grid]]){
    float x=a[g], y=a[g+1], z=a[g+2];
    o[g] = saturate(fma(x,y,z));
}
