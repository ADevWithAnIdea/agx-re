#include <metal_stdlib>
using namespace metal;
// isolate: precise:: namespace of every core SFU, distinct output slots
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    float x = a[i], y = b[i];
    o[i*11+0]  = precise::sin(x);
    o[i*11+1]  = precise::cos(x);
    o[i*11+2]  = precise::tan(x);
    o[i*11+3]  = precise::exp2(x);
    o[i*11+4]  = precise::log2(x);
    o[i*11+5]  = precise::sqrt(x);
    o[i*11+6]  = precise::rsqrt(x);
    o[i*11+7]  = precise::exp(x);
    o[i*11+8]  = precise::log(x);
    o[i*11+9]  = precise::pow(x, y);
    o[i*11+10] = precise::sinpi(x);
}
