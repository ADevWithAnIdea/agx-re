#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    float x=a[i];
    o[i] = floor(x)+ceil(x)+trunc(x)+rint(x)+fract(x)+abs(x)+sign(x);
}
