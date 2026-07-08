#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    float x=a[i];
    o[i] = exp2(x)+log2(x)+sqrt(x)+rsqrt(x)+(1.0f/x)+sin(x)+cos(x)+pow(x,2.5f)+exp(x)+log(x);
}
