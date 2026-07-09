#include <metal_stdlib>
using namespace metal;
// isolate: exp10 (float), one-arg SFU
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = exp10(a[i]);
}
