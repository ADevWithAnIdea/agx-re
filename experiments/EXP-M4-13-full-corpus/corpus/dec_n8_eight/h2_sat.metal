#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o[[buffer(0)]], device const half2* a[[buffer(1)]],
              device const half2* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = saturate(a[i] + b[i]);
}
