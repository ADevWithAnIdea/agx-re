#include <metal_stdlib>
using namespace metal;
// isolate: fast:: namespace of every core SFU, distinct output slots
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    float x = a[i], y = b[i];
    o[i*11+0]  = fast::sin(x);
    o[i*11+1]  = fast::cos(x);
    o[i*11+2]  = fast::tan(x);
    o[i*11+3]  = fast::exp2(x);
    o[i*11+4]  = fast::log2(x);
    o[i*11+5]  = fast::sqrt(x);
    o[i*11+6]  = fast::rsqrt(x);
    o[i*11+7]  = fast::exp(x);
    o[i*11+8]  = fast::log(x);
    o[i*11+9]  = fast::pow(x, y);
    o[i*11+10] = fast::sinpi(x);
}
