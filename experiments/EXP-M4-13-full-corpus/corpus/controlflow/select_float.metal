#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){
    float x=a[i], y=b[i];
    o[i] = (x<y) ? fma(x,y,1.0f) : (isnan(x) ? 0.0f : x/y);
}
