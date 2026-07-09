#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o[[buffer(0)]], device const half2* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = a[i] + half2(2.0h, 2.0h);
}
